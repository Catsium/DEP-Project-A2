"""Receive live Nesso BLE data and send it to FastAPI in batches."""

import asyncio
import os
import sys
import time

import httpx


# Only Flowery is connected while debugging.
DEVICE_NAMES = ["Flowery"]

# BLE characteristic used by the Nesso to send all 6 IMU values.
ACCEL_AND_GYRO_UUID = "f509416c-3c4b-401e-a768-b25a9e621a91"

SCAN_TIME_SECONDS = 10.0
SEND_INTERVAL_SECONDS = 1.0

# NESSO_API_URL should contain the full FastAPI POST URL.
API_URL = "https://siteguardbackend.onrender.com/data"
API_KEY = "playdeltarunetoday"


pending_batches = {}
sample_counts = {}
start_times = {}
last_receive_times = {}

for device_name in DEVICE_NAMES:
    pending_batches[device_name] = []
    sample_counts[device_name] = 0
    start_times[device_name] = None
    last_receive_times[device_name] = None


def decode_sensor_packet(data):
    """Convert one BLE packet into six sensor numbers."""
    raw_text = data.decode("utf-8").strip()
    raw_values = raw_text.split(",")

    if len(raw_values) != 6:
        raise ValueError("Expected six comma-separated sensor values.")

    sensor_values = []
    for raw_value in raw_values:
        sensor_values.append(float(raw_value))

    return sensor_values


def process_sensor_packet(device_name, data, receive_time=None):
    """Turn one BLE packet into one reading ready for FastAPI."""
    sensor_values = decode_sensor_packet(data)

    if receive_time is None:
        receive_time = time.perf_counter()

    if start_times[device_name] is None:
        start_times[device_name] = receive_time

    elapsed_time = receive_time - start_times[device_name]

    previous_receive_time = last_receive_times[device_name]
    if previous_receive_time is None:
        interval_ms = 0.0
    else:
        interval_ms = (receive_time - previous_receive_time) * 1000.0

    last_receive_times[device_name] = receive_time
    sample_counts[device_name] += 1

    reading = {
        "sample_no": sample_counts[device_name],
        "time": elapsed_time,
        "interval": interval_ms,
        "accel_x": sensor_values[0],
        "accel_y": sensor_values[1],
        "accel_z": sensor_values[2],
        "gyro_x": sensor_values[3],
        "gyro_y": sensor_values[4],
        "gyro_z": sensor_values[5],
    }

    pending_batches[device_name].append(reading)
    return reading


def build_payload(device_name, readings):
    """Build the JSON body expected by the FastAPI backend."""
    return {
        "device_id": device_name,
        "readings": readings,
    }


async def upload_pending_batches(http_client):
    """Send each Nesso's current readings to FastAPI."""
    headers = {
        "X-API-Key": API_KEY,
    }

    for device_name in DEVICE_NAMES:
        if len(pending_batches[device_name]) == 0:
            continue

        # Remove the current batch before sending so new BLE readings can
        # continue collecting while the request is in progress.
        batch = pending_batches[device_name]
        pending_batches[device_name] = []

        payload = build_payload(device_name, batch)

        try:
            response = await http_client.post(
                API_URL,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()

            print(
                f"Uploaded {len(batch)} readings from {device_name}."
            )

        except httpx.HTTPError as error:
            # Keep failed readings so they can be retried on the next upload.
            pending_batches[device_name] = (
                batch + pending_batches[device_name]
            )

            print(
                f"Could not upload {device_name} data | {error}"
            )


async def send_batches_to_api():
    """Send accumulated readings approximately once per second."""
    async with httpx.AsyncClient(timeout=10.0) as http_client:
        try:
            while True:
                await asyncio.sleep(SEND_INTERVAL_SECONDS)
                await upload_pending_batches(http_client)

        except asyncio.CancelledError:
            # Try to send the final partial batch before the program closes.
            await upload_pending_batches(http_client)
            raise


def create_notification_handler(device_name):
    """Create a BLE notification function for one Nesso."""
    def notification_handler(characteristic, data):
        try:
            process_sensor_packet(device_name, data)
        except (UnicodeDecodeError, ValueError) as error:
            print(f"{device_name} | Invalid sensor packet | {error}")
        except Exception as error:
            print(f"{device_name} | Error processing sensor packet | {error}")

    return notification_handler


async def receive_from_device(device_name, device, bleak_client):
    """Connect to one Nesso and keep receiving BLE notifications."""
    try:
        async with bleak_client(device, timeout=20.0) as client:
            print(f"Connected to {device_name} [{device.address}]")

            characteristic = client.services.get_characteristic(
                ACCEL_AND_GYRO_UUID
            )

            if characteristic is None:
                print(f"{device_name} | Sensor characteristic was not found.")
                return

            if "notify" not in characteristic.properties:
                print(f"{device_name} | Sensor notifications are not supported.")
                return

            notification_handler = create_notification_handler(device_name)
            await client.start_notify(characteristic, notification_handler)

            while client.is_connected:
                await asyncio.sleep(1)

            print(f"Disconnected from {device_name}.")

    except asyncio.CancelledError:
        raise
    except Exception as error:
        print(f"Could not receive from {device_name} | {error}")


async def run_sender():
    """Find the configured Nessos, receive their data, and send it to FastAPI."""
    if not API_URL or not API_KEY:
        print("NESSO_API_URL and NESSO_API_KEY must both be set.")
        return

    try:
        from bleak import BleakClient, BleakScanner
    except ImportError:
        print("Bleak is required for Bluetooth connections.")
        print("Install it with: python -m pip install bleak")
        return

    configured_device_names = ", ".join(DEVICE_NAMES)
    print(f"Scanning for {configured_device_names}...")

    discovered_devices = await BleakScanner.discover(
        timeout=SCAN_TIME_SECONDS
    )

    devices_by_name = {}
    for device in discovered_devices:
        if device.name in DEVICE_NAMES:
            devices_by_name[device.name] = device

    connection_tasks = []

    for device_name in DEVICE_NAMES:
        if device_name not in devices_by_name:
            print(f"{device_name} was not found.")
            continue

        connection_tasks.append(
            receive_from_device(
                device_name,
                devices_by_name[device_name],
                BleakClient,
            )
        )

    if not connection_tasks:
        print("No configured Nessos were found.")
        return

    sender_task = asyncio.create_task(send_batches_to_api())

    print("Sending Nesso data to FastAPI. Press Ctrl+C to stop.")

    try:
        await asyncio.gather(*connection_tasks)
    finally:
        sender_task.cancel()
        try:
            await sender_task
        except asyncio.CancelledError:
            pass


def reset_sender_state():
    """Reset local state used by the offline self-check."""
    for device_name in DEVICE_NAMES:
        pending_batches[device_name] = []
        sample_counts[device_name] = 0
        start_times[device_name] = None
        last_receive_times[device_name] = None


def run_self_check():
    """Test packet decoding and FastAPI payload creation without a Nesso."""
    reset_sender_state()

    device_name = DEVICE_NAMES[0]
    packet = b"0.1,0.2,1.0,10.0,20.0,30.0"

    first_reading = process_sensor_packet(
        device_name,
        packet,
        receive_time=100.00,
    )
    second_reading = process_sensor_packet(
        device_name,
        packet,
        receive_time=100.05,
    )

    assert first_reading["sample_no"] == 1
    assert first_reading["time"] == 0.0
    assert first_reading["interval"] == 0.0

    assert second_reading["sample_no"] == 2
    assert abs(second_reading["time"] - 0.05) < 0.000001
    assert abs(second_reading["interval"] - 50.0) < 0.000001

    payload = build_payload(
        device_name,
        list(pending_batches[device_name]),
    )

    assert payload["device_id"] == device_name
    assert len(payload["readings"]) == 2

    expected_fields = {
        "sample_no",
        "time",
        "interval",
        "accel_x",
        "accel_y",
        "accel_z",
        "gyro_x",
        "gyro_y",
        "gyro_z",
    }
    assert set(payload["readings"][0].keys()) == expected_fields

    try:
        decode_sensor_packet(b"1,2,3")
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid BLE packets must be rejected.")

    print("Self-check passed for BLE decoding and FastAPI payload creation.")

async def run_api_check():
    """Send fake Nesso readings through FastAPI to the database."""
    if not API_URL or not API_KEY:
        print("API_URL or API_KEY is not set.")
        return

    reset_sender_state()

    device_name = DEVICE_NAMES[0]

    # Create two fake BLE packets.
    process_sensor_packet(
        device_name,
        b"0.1,0.2,1.0,10.0,20.0,30.0",
        receive_time=100.00,
    )

    process_sensor_packet(
        device_name,
        b"0.2,0.3,0.9,11.0,21.0,31.0",
        receive_time=100.05,
    )

    async with httpx.AsyncClient(timeout=60.0) as http_client:
        await upload_pending_batches(http_client)

    print("API check finished.")

if __name__ == "__main__":
    if "--self-check" in sys.argv:
        run_self_check()

    elif "--api-check" in sys.argv:
        asyncio.run(run_api_check())

    else:
        try:
            asyncio.run(run_sender())
        except KeyboardInterrupt:
            print("\nSender stopped by user.")
