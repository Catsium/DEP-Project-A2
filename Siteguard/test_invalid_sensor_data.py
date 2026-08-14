import os
import httpx

API_URL = "https://siteguardbackend.onrender.com/data"
API_KEY = os.getenv("NESSO_API_KEY")

payload = {
    "device_id": "InvalidDataTest",
    "readings": [
        {
            "sample_no": 1,
            "time": 0.0,
            "interval": 0.1,
            "accel_x": 0.0,
            "accel_y": 0.0,

            # accel_z intentionally missing

            "gyro_x": 0.0,
            "gyro_y": 0.0,
            "gyro_z": 0.0
        }
    ]
}

response = httpx.post(
    API_URL,
    json=payload,
    headers={"X-API-Key": API_KEY},
    timeout=30.0
)

print("Status:", response.status_code)
print("Response:", response.text)