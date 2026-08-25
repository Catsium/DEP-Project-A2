import os
import time
from datetime import datetime

import httpx
from dotenv import load_dotenv


load_dotenv()


API_URL = "https://siteguardbackend.onrender.com/data"
API_KEY = os.getenv("NESSO_API_KEY")


if not API_KEY:
    raise RuntimeError("NESSO_API_KEY is not set")


DEVICES = [
    "Catsium",
    "Doggsium",
    "Birdsium"
]


# Give this simulator run its own session.
session_time = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)


session_ids = {
    device: f"sim_{device}_{session_time}"
    for device in DEVICES
}


sample_numbers = {
    device: 1
    for device in DEVICES
}


def make_readings(device):

    readings = []

    start_sample = sample_numbers[device]


    for i in range(15):

        sample_no = start_sample + i

        readings.append({
            "sample_no": sample_no,

            # Nesso normally samples at 10 Hz.
            "time": sample_no * 0.1,
            "interval": 0.1,

            # Simple stationary worker.
            "accel_x": 0.0,
            "accel_y": 0.0,
            "accel_z": 1.0,

            "gyro_x": 0.0,
            "gyro_y": 0.0,
            "gyro_z": 0.0
        })


    sample_numbers[device] += 15

    return readings


def send_device(device):

    body = {
        "device_id": device,
        "session_id": session_ids[device],
        "readings": make_readings(device)
    }


    response = httpx.post(
        API_URL,

        headers={
            "x-api-key": API_KEY
        },

        json=body,

        timeout=20
    )


    response.raise_for_status()

    result = response.json()


    print(
        f"{device} | "
        f"readings={result['readings_saved']} | "
        f"predictions={result['predictions_saved']}"
    )


print("Starting SiteGuard Nesso simulator")
print("Press Ctrl+C to stop.")
print()


try:

    while True:

        for device in DEVICES:

            try:
                send_device(device)

            except Exception as error:

                print(
                    f"{device} failed | {error}"
                )


        # 15 samples at 10 Hz represents
        # roughly 1.5 seconds of sensor data.
        time.sleep(1.5)


except KeyboardInterrupt:

    print()
    print("Simulator stopped.")