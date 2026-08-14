import os
from datetime import datetime
import httpx
from dotenv import load_dotenv

load_dotenv()

API_URL = "https://siteguardbackend.onrender.com/data"
DEVICE_ID = "Flowery"
API_KEY = os.getenv("NESSO_API_KEY")

if not API_KEY:
    raise RuntimeError("NESSO_API_KEY is not set")

DEVICE_ID = "Flowery"
SESSION_ID = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

TOTAL_READINGS = 80
BATCH_SIZE = 20


readings = []

for sample_no in range(1, TOTAL_READINGS + 1):

    reading = {
        "sample_no": sample_no,
        "time": (sample_no - 1) * 0.05,
        "interval": 50.0,
        "accel_x": 0.0,
        "accel_y": 0.0,
        "accel_z": 1.0,
        "gyro_x": 0.0,
        "gyro_y": 0.0,
        "gyro_z": 0.0,
    }

    readings.append(reading)


headers = {
    "X-API-Key": API_KEY
}


for start in range(0, TOTAL_READINGS, BATCH_SIZE):

    batch = readings[start:start + BATCH_SIZE]

    payload = {
        "device_id": DEVICE_ID,
        "session_id": SESSION_ID,
        "readings": batch,
    }

    response = httpx.post(
        API_URL,
        json=payload,
        headers=headers,
        timeout=30.0,
    )

    print(
        f"Sent samples "
        f"{batch[0]['sample_no']}-{batch[-1]['sample_no']}"
    )

    print(
        "Status:",
        response.status_code
    )

    print(
        "Response:",
        response.json()
    )

    print()