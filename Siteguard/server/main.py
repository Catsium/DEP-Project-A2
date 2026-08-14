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
    readings: list[Reading]


@app.get("/")
def home():
    return {"status": "SiteGuard API is running"}


@app.post("/data")
def receive_data(data: NessoData, x_api_key: str = Header(None)):

    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    db = SessionLocal()

    reading_dicts = [
        reading.model_dump()
        for reading in data.readings
    ]

    # ---------------------------------
    # 1. Save raw sensor readings first
    # ---------------------------------
    try:
        for reading in reading_dicts:
            save_reading(
                db,
                data.device_id,
                reading
            )

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
        for reading in reading_dicts:

            add_reading(
                data.device_id,
                reading
            )

            # Only create a new prediction opportunity
            # every 15 readings.
            if reading["sample_no"] % PREDICTION_INTERVAL != 0:
                continue

            prediction = predict_device(
                data.device_id
            )

            # Buffer does not have 45 readings yet.
            if prediction is None:
                continue

            vote_result = vote_prediction(
                data.device_id,
                prediction
            )

            print(
                f"{data.device_id} | "
                f"Rule: {prediction['rule_prediction']} | "
                f"ML: {prediction['ml_prediction']} | "
                f"Status: {vote_result['decision_status']} | "
                f"Final: {vote_result['final_prediction']}"
            )

            # PENDING is kept in memory.
            # Only resolved predictions go to Supabase.
            if vote_result["decision_status"] == "PENDING":
                continue

            save_prediction(
                db,
                data.device_id,
                vote_result
            )

            db.commit()

            predictions_saved += 1

    except Exception as error:
        db.rollback()

        # Important:
        # raw readings were already committed,
        # so prediction failure must NOT make
        # the sender resend the raw batch.
        print("PREDICTION ERROR:", error)

    finally:
        db.close()

    return {
        "status": "success",
        "device_id": data.device_id,
        "readings_saved": len(data.readings),
        "predictions_saved": predictions_saved
    }