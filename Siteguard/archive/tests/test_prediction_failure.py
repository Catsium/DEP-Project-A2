import os
from datetime import datetime

import httpx
from datetime import datetime

API_URL = "https://siteguardbackend.onrender.com/data"
API_KEY = os.getenv("NESSO_API_KEY")

DEVICE_ID = "PredictionFailure_" + datetime.now().strftime("%Y%m%d_%H%M%S")
SESSION_ID = datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def make_reading(sample_no):
    interval = 100.0

    # Deliberately create one invalid sensor gap.
    # This will be inside the first prediction's target window.
    if sample_no == 20:
        interval = 600.0

    return {
        "sample_no": sample_no,
        "time": sample_no * 0.1,
        "interval": interval,
        "accel_x": 0.0,
        "accel_y": 0.0,
        "accel_z": 1.0,
        "gyro_x": 0.0,
        "gyro_y": 0.0,
        "gyro_z": 0.0,
    }


headers = {
    "X-API-Key": API_KEY
}


for start in range(1, 61, 15):

    readings = [
        make_reading(sample_no)
        for sample_no in range(start, start + 15)
    ]

    payload = {
        "device_id": DEVICE_ID,
        "session_id": SESSION_ID,
        "readings": readings
    }

    response = httpx.post(
        API_URL,
        json=payload,
        headers=headers,
        timeout=30.0
    )

    print(
        f"Samples {start}-{start + 14}:",
        response.status_code,
        response.json()
    )


print()
print("Device ID:", DEVICE_ID)