from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
import os

from database import SessionLocal
from crud import save_reading, save_prediction

from prediction_buffer import add_reading
from combined_predictor import predict_device
from prediction_voter import vote_prediction

PREDICTION_INTERVAL = 15
app = FastAPI()

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

    # Keep prediction state separate for every
    # device session.
    state_key = (
        f"{data.device_id}::{data.session_id}"
    )

    # Only readings that were genuinely inserted
    # should enter the prediction buffer.
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

            # Only create a prediction opportunity
            # every 15 readings.
            if (
                reading["sample_no"]
                % PREDICTION_INTERVAL
                != 0
            ):
                continue

            prediction = predict_device(
                state_key
            )

            # Buffer does not have 45 readings yet.
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

            # PENDING is kept in memory.
            # Only resolved predictions go to Supabase.
            if (
                vote_result["decision_status"]
                == "PENDING"
            ):
                continue

            was_inserted = save_prediction(
                db,
                data.device_id,
                data.session_id,
                vote_result
            )

            db.commit()

            if was_inserted:
                predictions_saved += 1

    except Exception as error:
        db.rollback()

        # Raw readings were already committed.
        # Prediction failure must not cause the
        # sender to resend raw data.
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