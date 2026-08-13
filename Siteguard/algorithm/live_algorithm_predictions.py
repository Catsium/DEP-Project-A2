"""Receive live data from four Nessos and run algorithm-only predictions."""

import asyncio
import json
import sys
import threading
import time
import webbrowser
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PROJECT_FOLDER = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_FOLDER))

from live_prediction import RollingPredictor, load_model_bundle

from detection_algorithm import WINDOW_SIZE, classify_sensor_window

# Only Flowery is connected while debugging.
DEVICE_NAMES = ["Flowery"]
DASHBOARD_DEVICE_NAMES = ["Kris", "Susie", "Ralsei", "Flowery"]
ACCEL_AND_GYRO_UUID = "f509416c-3c4b-401e-a768-b25a9e621a91"
SCAN_TIME_SECONDS = 10.0
PREDICTION_STEP = 5
MINIMUM_READINGS = WINDOW_SIZE * 2
FULL_CONTEXT_READINGS = WINDOW_SIZE * 3
DASHBOARD_HOST = "127.0.0.1"
DASHBOARD_PORT = 8000
DASHBOARD_FILE = Path(__file__).with_name("live_dashboard.html")


device_windows = {}
last_receive_times = {}
readings_since_prediction = {}
connection_states = {}
latest_predictions = {}
dashboard_lock = threading.Lock()
device_windows = {}
last_receive_times = {}
model = None
metadata = None
ml_predictors = {}

for device_name in DASHBOARD_DEVICE_NAMES:
    connection_states[device_name] = "Not connected"

for device_name in DEVICE_NAMES:
    device_windows[device_name] = deque(maxlen=FULL_CONTEXT_READINGS)
    last_receive_times[device_name] = None
    readings_since_prediction[device_name] = 0
    connection_states[device_name] = "Waiting"

def initialise_ml_predictors():
    global model
    global metadata

    model, metadata = load_model_bundle(PROJECT_FOLDER)

    for device_name in DEVICE_NAMES:
        ml_predictors[device_name] = RollingPredictor(
            model,
            metadata,
        )

    print("ML model loaded.")

def decode_sensor_packet(data):
    raw_text = data.decode("utf-8").strip()
    raw_values = raw_text.split(",")

    if len(raw_values) != 6:
        raise ValueError("Expected six comma-separated sensor values.")

    sensor_values = []
    for raw_value in raw_values:
        sensor_values.append(float(raw_value))

    return sensor_values


def process_sensor_packet(device_name, data, receive_time=None):
    sensor_values = decode_sensor_packet(data)

    if receive_time is None:
        receive_time = time.perf_counter()

    previous_receive_time = last_receive_times[device_name]
    if previous_receive_time is None:
        interval_ms = ""
    else:
        interval_ms = (receive_time - previous_receive_time) * 1000.0

    last_receive_times[device_name] = receive_time

    sensor_reading = {
        "interval": interval_ms,
        "accel_x": sensor_values[0],
        "accel_y": sensor_values[1],
        "accel_z": sensor_values[2],
        "gyro_x": sensor_values[3],
        "gyro_y": sensor_values[4],
        "gyro_z": sensor_values[5],
    }

    device_windows[device_name].append(sensor_reading)
    readings_since_prediction[device_name] += 1

    if len(device_windows[device_name]) < MINIMUM_READINGS:
        return None

    if readings_since_prediction[device_name] < PREDICTION_STEP:
        return None

    readings_since_prediction[device_name] = 0
    all_readings = list(device_windows[device_name])

    if len(all_readings) >= FULL_CONTEXT_READINGS:
        window_start = WINDOW_SIZE
    else:
        window_start = len(all_readings) - MINIMUM_READINGS

    current_window = all_readings[
        window_start:window_start + WINDOW_SIZE
    ]

    return classify_sensor_window(current_window)


def print_prediction(device_name, prediction):
    current_time = datetime.now().strftime("%H:%M:%S")

    with dashboard_lock:
        latest_predictions[device_name] = {
            "time": current_time,
            "status": prediction["status"],
            "reason": prediction["reason"],
            "category": prediction["category"],
            "subtype": prediction["subtype"],
            "feature_values": prediction["feature_values"],
        }

    if prediction["status"] == "INSUFFICIENT_DATA":
        print(
            f"{current_time} | {device_name} | "
            f"INSUFFICIENT_DATA | {prediction['reason']}"
        )
        return

    category = prediction["category"]
    subtype = prediction["subtype"]
    impact = prediction["feature_values"]["impact"]
    freefall = prediction["feature_values"]["freefall"]
    motion = prediction["feature_values"]["motion_standard_deviation"]

    print(
        f"{current_time} | {device_name} | "
        f"{category} -> {subtype} | impact={impact:.2f} "
        f"freefall={freefall:.2f} motion={motion:.2f}"
    )


def set_connection_state(device_name, connection_state):
    with dashboard_lock:
        connection_states[device_name] = connection_state


def get_dashboard_data():
    with dashboard_lock:
        devices = {}
        for device_name in DASHBOARD_DEVICE_NAMES:
            devices[device_name] = {
                "connection": connection_states[device_name],
                "prediction": latest_predictions.get(device_name),
            }

    return {"devices": devices}


class DashboardRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/predictions":
            response_body = json.dumps(get_dashboard_data()).encode("utf-8")
            content_type = "application/json; charset=utf-8"
        elif self.path == "/" or self.path == "/index.html":
            response_body = DASHBOARD_FILE.read_bytes()
            content_type = "text/html; charset=utf-8"
        else:
            self.send_error(404)
            return

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

    def log_message(self, message_format, *message_arguments):
        return


def start_dashboard(open_browser=True):
    try:
        dashboard_server = ThreadingHTTPServer(
            (DASHBOARD_HOST, DASHBOARD_PORT),
            DashboardRequestHandler,
        )
    except OSError as error:
        print(f"Could not start dashboard | {error}")
        return None

    dashboard_thread = threading.Thread(
        target=dashboard_server.serve_forever,
        daemon=True,
    )
    dashboard_thread.start()

    dashboard_url = f"http://{DASHBOARD_HOST}:{DASHBOARD_PORT}"
    print(f"Live dashboard: {dashboard_url}")

    if open_browser:
        webbrowser.open(dashboard_url)

    return dashboard_server


def create_notification_handler(device_name):
    def notification_handler(characteristic, data):
        try:
            prediction = process_sensor_packet(device_name, data)
            if prediction is not None:
                print_prediction(device_name, prediction)
        except (UnicodeDecodeError, ValueError) as error:
            print(f"{device_name} | Invalid sensor packet | {error}")
        except Exception as error:
            print(f"{device_name} | Error processing sensor packet | {error}")

    return notification_handler


async def receive_from_device(device_name, device, bleak_client):
    try:
        async with bleak_client(device, timeout=20.0) as client:
            set_connection_state(device_name, "Connected")
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

            set_connection_state(device_name, "Disconnected")
            print(f"Disconnected from {device_name}.")

    except asyncio.CancelledError:
        raise
    except Exception as error:
        set_connection_state(device_name, "Connection error")
        print(f"Could not receive from {device_name} | {error}")


async def run_live_predictions():
    try:
        from bleak import BleakClient, BleakScanner
    except ImportError:
        print("Bleak is required for Bluetooth connections.")
        print("Install it with: python -m pip install bleak")
        raise SystemExit(1)

    dashboard_server = start_dashboard()
    initialise_ml_predictors()

    try:
        configured_device_names = ", ".join(DEVICE_NAMES)
        print(f"Scanning for {configured_device_names}...")
        discovered_devices = await BleakScanner.discover(timeout=SCAN_TIME_SECONDS)

        devices_by_name = {}
        for device in discovered_devices:
            if device.name in DEVICE_NAMES:
                devices_by_name[device.name] = device

        connection_tasks = []
        for device_name in DEVICE_NAMES:
            if device_name not in devices_by_name:
                set_connection_state(device_name, "Not found")
                print(f"{device_name} was not found.")
                continue

            connection_task = receive_from_device(
                device_name,
                devices_by_name[device_name],
                BleakClient,
            )
            connection_tasks.append(connection_task)

        if not connection_tasks:
            print("No configured Nessos were found.")
            return

        print("Starting live algorithm predictions. Press Ctrl+C to stop.")
        await asyncio.gather(*connection_tasks)
    finally:
        if dashboard_server is not None:
            dashboard_server.shutdown()
            dashboard_server.server_close()


def reset_device_state():
    for device_name in DASHBOARD_DEVICE_NAMES:
        connection_states[device_name] = "Not connected"

    for device_name in DEVICE_NAMES:
        device_windows[device_name].clear()
        last_receive_times[device_name] = None
        readings_since_prediction[device_name] = 0
        connection_states[device_name] = "Waiting"

    latest_predictions.clear()


def run_self_check():
    reset_device_state()

    stationary_packet = b"0.0,0.0,1.0,0.0,0.0,0.0"
    test_device_name = DEVICE_NAMES[0]
    first_prediction = None

    for reading_number in range(MINIMUM_READINGS):
        receive_time = reading_number * 0.1
        first_prediction = process_sensor_packet(
            test_device_name,
            stationary_packet,
            receive_time,
        )

    assert first_prediction["subtype"] == "STATIONARY"
    assert len(device_windows[test_device_name]) == MINIMUM_READINGS

    for device_name in DEVICE_NAMES[1:]:
        assert len(device_windows[device_name]) == 0

    reset_device_state()

    next_prediction = None

    for reading_number in range(MINIMUM_READINGS):
        if reading_number == 7:
            packet = b"0.0,0.0,2.0,0.0,0.0,0.0"
        else:
            packet = stationary_packet

        next_prediction = process_sensor_packet(
            test_device_name,
            packet,
            reading_number * 0.1,
        )

    assert next_prediction["category"] == "FALL"
    assert next_prediction["subtype"] == "STF"

    try:
        decode_sensor_packet(b"1,2,3")
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid packets must be rejected.")

    print_prediction(test_device_name, next_prediction)
    dashboard_data = get_dashboard_data()
    saved_prediction = dashboard_data["devices"][test_device_name]["prediction"]
    assert saved_prediction["subtype"] == "STF"

    for device_name in DASHBOARD_DEVICE_NAMES:
        if device_name not in DEVICE_NAMES:
            assert dashboard_data["devices"][device_name]["connection"] == (
                "Not connected"
            )

    reset_device_state()
    print("Self-check passed for live parsing, buffers, dashboard, and predictions.")


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        run_self_check()
    else:
        try:
            asyncio.run(run_live_predictions())
        except KeyboardInterrupt:
            print("\nLive predictions stopped by user.")
