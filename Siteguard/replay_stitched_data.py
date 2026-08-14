"""Replay the stitched real Nesso dataset through the deployed SiteGuard API."""

import csv
import os
from datetime import datetime
from pathlib import Path

import httpx


BASE_URL = "https://siteguardbackend.onrender.com"
API_URL = BASE_URL + "/data"

CSV_FILE = Path(__file__).with_name("stitched_walking_stationary_ffh.csv")
BATCH_SIZE = 15

# A new device ID is used every run so an old Render buffer cannot affect
# the current test.
DEVICE_ID = "StitchedFFH_" + datetime.now().strftime("%Y%m%d_%H%M%S")

API_KEY = os.getenv("NESSO_API_KEY")


if not API_KEY:
    print("NESSO_API_KEY is not set.")
    print('PowerShell example:')
    print('$env:NESSO_API_KEY="your_api_key_here"')
    raise SystemExit(1)


def load_readings():
    readings = []

    with CSV_FILE.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        for row in reader:
            readings.append(
                {
                    "sample_no": int(row["sample_no"]),
                    "time": float(row["time"]),
                    "interval": float(row["interval"]),
                    "accel_x": float(row["accel_x"]),
                    "accel_y": float(row["accel_y"]),
                    "accel_z": float(row["accel_z"]),
                    "gyro_x": float(row["gyro_x"]),
                    "gyro_y": float(row["gyro_y"]),
                    "gyro_z": float(row["gyro_z"]),
                }
            )

    return readings


def main():
    readings = load_readings()

    headers = {
        "X-API-Key": API_KEY,
    }

    print("Device ID:", DEVICE_ID)
    print("Readings:", len(readings))
    print()

    # Wake Render first. This avoids the normal cold-start timeout.
    print("Waking Render...")
    response = httpx.get(BASE_URL + "/", timeout=90.0)
    response.raise_for_status()
    print("Render:", response.json())
    print()

    for start in range(0, len(readings), BATCH_SIZE):
        batch = readings[start:start + BATCH_SIZE]

        payload = {
            "device_id": DEVICE_ID,
            "readings": batch,
        }

        response = httpx.post(
            API_URL,
            json=payload,
            headers=headers,
            timeout=90.0,
        )

        print(
            f"Sent samples "
            f"{batch[0]['sample_no']}-{batch[-1]['sample_no']}"
        )
        print("Status:", response.status_code)

        if response.is_success:
            print("Response:", response.json())
        else:
            print("Response:", response.text)
            response.raise_for_status()

        print()

    print("Replay finished.")
    print("Use this device_id in Supabase:")
    print(DEVICE_ID)


if __name__ == "__main__":
    main()
