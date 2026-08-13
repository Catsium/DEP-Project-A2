from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
import os

from database import SessionLocal
from crud import save_reading


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

    try:
        for reading in data.readings:
            save_reading(
                db,
                data.device_id,
                reading.model_dump()
            )

        db.commit()

        return {
            "status": "success",
            "device_id": data.device_id,
            "readings_saved": len(data.readings)
        }

    except Exception as e:
        db.rollback()
        print("DATABASE ERROR:", e)

        raise HTTPException(
            status_code=500,
            detail="Failed to save readings"
        )

    finally:
        db.close()
        #test