import os
from datetime import datetime

import httpx


API_URL = "https://siteguardbackend.onrender.com/data"
API_KEY = os.getenv("NESSO_API_KEY")

DEVICE_ID = "DuplicateRetryTest"
SESSION_ID = datetime.now().strftime("%Y%m%d_%H%M%S_%f")


readings = []

for sample_no in range(1, 46):
    readings.append(
        {
            "sample_no": sample_no,
            "time": (sample_no - 1) * 0.1,
            "interval": 0.0 if sample_no == 1 else 100.0,
            "accel_x": 0.0,
            "accel_y": 0.0,
            "accel_z": 1.0,
            "gyro_x": 0.0,
            "gyro_y": 0.0,
            "gyro_z": 0.0,
        }
    )


payload = {
    "device_id": DEVICE_ID,
    "session_id": SESSION_ID,
    "readings": readings,
}

headers = {
    "X-API-Key": API_KEY
}


print("Session:", SESSION_ID)

print("\nFIRST SEND")

response = httpx.post(
    API_URL,
    json=payload,
    headers=headers,
    timeout=90.0
)

print(response.status_code)
print(response.json())


print("\nEXACT SAME SEND AGAIN")

response = httpx.post(
    API_URL,
    json=payload,
    headers=headers,
    timeout=90.0
)

print(response.status_code)
print(response.json())