from fastapi import FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime, timezone
from threading import Lock
import json
import os
import queue
from dotenv import load_dotenv

load_dotenv()

from database import SessionLocal
from crud import save_reading, save_prediction

from dashboard_queries import (
    get_recent_safety_events,
    get_dashboard_devices,
    get_device_details,
    get_incident_details,
    get_dashboard_summary,
    get_dashboard_insights,
    resolve_incident
)

from prediction_buffer import add_reading
from combined_predictor import predict_device
from prediction_voter import vote_prediction

PREDICTION_INTERVAL = 15
app = FastAPI()


# Connected dashboard SSE listeners.
critical_alert_listeners = []
critical_alert_lock = Lock()


def broadcast_critical_alert(alert):

    with critical_alert_lock:
        listeners = list(
            critical_alert_listeners
        )

    for listener in listeners:

        try:
            listener.put_nowait(alert)

        except queue.Full:
            pass


# Dashboard folder
DASHBOARD_DIR = (
    Path(__file__).resolve().parent
    / "dashboard"
)

app.mount(
    "/dashboard",
    StaticFiles(
        directory=str(DASHBOARD_DIR),
        html=True
    ),
    name="dashboard"
)


API_KEY = os.getenv("NESSO_API_KEY")

if not API_KEY:
    raise RuntimeError("NESSO_API_KEY is not set")


class Reading(BaseModel):
    sample_no: int
    time: float
    interval: float

    accel_x: float
    accel_y: float
    accel_z: float

    gyro_x: float
    gyro_y: float
    gyro_z: float


class NessoData(BaseModel):
    device_id: str
    session_id: str
    readings: list[Reading]


@app.get("/")
def home():
    return {"status": "SiteGuard API is running"}

@app.get("/api/dashboard/events")
def dashboard_events():

    db = SessionLocal()

    try:
        events = get_recent_safety_events(db)
        return events

    except Exception as error:

        print("DASHBOARD DATABASE ERROR:", error)

        raise HTTPException(
            status_code=500,
            detail="Failed to load dashboard events"
        )

    finally:
        db.close()
@app.get("/api/dashboard/devices")
def dashboard_devices():

    db = SessionLocal()

    try:
        devices = get_dashboard_devices(db)
        return devices

    except Exception as error:

        print("DASHBOARD DEVICE ERROR:", error)

        raise HTTPException(
            status_code=500,
            detail="Failed to load dashboard devices"
        )

    finally:
        db.close()

@app.get(
    "/api/dashboard/incidents/{prediction_id}"
)
def dashboard_incident_details(
    prediction_id: int
):

    db = SessionLocal()

    try:

        incident = get_incident_details(
            db,
            prediction_id
        )

        if incident is None:

            raise HTTPException(
                status_code=404,
                detail="Incident not found"
            )

        return incident


    except HTTPException:
        raise


    except Exception as error:

        print(
            "DASHBOARD INCIDENT ERROR:",
            error
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to load incident"
        )

    finally:
        db.close()

@app.get("/api/dashboard/device/{device_id}")
def dashboard_device_details(device_id: str):

    db = SessionLocal()

    try:
        details = get_device_details(
            db,
            device_id
        )

        if details is None:
            raise HTTPException(
                status_code=404,
                detail="Device not found"
            )

        return details

    except HTTPException:
        raise

    except Exception as error:

        print(
            "DASHBOARD DEVICE DETAILS ERROR:",
            error
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to load device details"
        )

    finally:
        db.close()

@app.get("/api/dashboard/summary")
def dashboard_summary():

    db = SessionLocal()

    try:

        summary = get_dashboard_summary(db)

        return summary

    except Exception as error:

        print(
            "DASHBOARD SUMMARY ERROR:",
            error
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to load dashboard summary"
        )

    finally:
        db.close()

@app.get("/api/dashboard/insights")
def dashboard_insights(
    device: str = "All",
    event: str = "All",
    days: int = 7
):

    if days not in (1, 7):
        days = 7

    db = SessionLocal()

    try:

        insights = get_dashboard_insights(
            db,
            device,
            event,
            days
        )

        return insights

    except Exception as error:

        print(
            "DASHBOARD INSIGHTS ERROR:",
            error
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to load dashboard insights"
        )

    finally:
        db.close()

@app.get("/api/dashboard/alerts/stream")
def dashboard_alert_stream():

    listener = queue.Queue(
        maxsize=20
    )

    with critical_alert_lock:
        critical_alert_listeners.append(
            listener
        )


    def event_stream():

        try:

            # Ask the browser to reconnect quickly
            # if the connection drops.
            yield "retry: 1000\n\n"

            while True:

                try:

                    alert = listener.get(
                        timeout=15
                    )

                    yield (
                        "data: "
                        + json.dumps(alert)
                        + "\n\n"
                    )

                except queue.Empty:

                    # Keep proxies / browsers from
                    # treating the stream as idle.
                    yield ": keep-alive\n\n"


        finally:

            with critical_alert_lock:

                if (
                    listener
                    in critical_alert_listeners
                ):
                    critical_alert_listeners.remove(
                        listener
                    )


    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )


@app.patch(
    "/api/dashboard/incidents/{prediction_id}/resolve"
)
def dashboard_resolve_incident(
    prediction_id: int
):

    db = SessionLocal()

    try:

        incident = resolve_incident(
            db,
            prediction_id
        )

        if incident is None:

            raise HTTPException(
                status_code=404,
                detail="Incident not found"
            )

        db.commit()

        return dict(incident)


    except HTTPException:

        db.rollback()
        raise


    except Exception as error:

        db.rollback()

        print(
            "DASHBOARD RESOLVE ERROR:",
            error
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to resolve incident"
        )


    finally:
        db.close()

@app.post("/data")
def receive_data(data: NessoData, x_api_key: str = Header(None)):

    if x_api_key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    db = SessionLocal()

    reading_dicts = [
        reading.model_dump()
        for reading in data.readings
    ]

    state_key = (
        f"{data.device_id}::{data.session_id}"
    )

    new_readings = []

    # ---------------------------------
    # 1. Save raw sensor readings first
    # ---------------------------------
    try:
        for reading in reading_dicts:

            was_inserted = save_reading(
                db,
                data.device_id,
                data.session_id,
                reading
            )

            if was_inserted:
                new_readings.append(reading)

        db.commit()

    except Exception as error:
        db.rollback()
        db.close()

        print("RAW DATABASE ERROR:", error)

        raise HTTPException(
            status_code=500,
            detail="Failed to save readings"
        )


    # ---------------------------------
    # 2. Run predictions afterwards
    # ---------------------------------
    predictions_saved = 0

    try:
        for reading in new_readings:

            add_reading(
                state_key,
                reading
            )

            if (
                reading["sample_no"]
                % PREDICTION_INTERVAL
                != 0
            ):
                continue

            prediction = predict_device(
                state_key
            )

            if prediction is None:
                continue

            vote_result = vote_prediction(
                state_key,
                prediction
            )

            print(
                f"{data.device_id} | "
                f"Session: {data.session_id} | "
                f"Rule: "
                f"{prediction['rule_prediction']} | "
                f"ML: "
                f"{prediction['ml_prediction']} | "
                f"Status: "
                f"{vote_result['decision_status']} | "
                f"Final: "
                f"{vote_result['final_prediction']}"
            )

            if (
                vote_result["decision_status"]
                == "PENDING"
            ):
                continue

            prediction_id = save_prediction(
                db,
                data.device_id,
                data.session_id,
                vote_result
            )

            db.commit()

            if prediction_id is not None:

                predictions_saved += 1

                if (
                    vote_result["final_prediction"]
                    in ("FFH", "STF")
                ):

                    broadcast_critical_alert({
                        "id": prediction_id,
                        "device_id":
                            data.device_id,
                        "final_prediction":
                            vote_result[
                                "final_prediction"
                            ],
                        "ml_confidence":
                            vote_result[
                                "ml_confidence"
                            ],
                        "decision_status":
                            vote_result[
                                "decision_status"
                            ],
                        "review_status":
                            "OPEN",
                        "created_at":
                            datetime.now(
                                timezone.utc
                            ).isoformat()
                    })

    except Exception as error:
        db.rollback()

        print("PREDICTION ERROR:", error)

    finally:
        db.close()


    return {
        "status": "success",
        "device_id": data.device_id,
        "session_id": data.session_id,
        "readings_saved": len(new_readings),
        "predictions_saved": predictions_saved
    }