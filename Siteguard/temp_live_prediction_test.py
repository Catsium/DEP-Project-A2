import asyncio
import sys
from pathlib import Path

from bleak import BleakClient, BleakScanner


PROJECT_ROOT = Path(__file__).resolve().parent
SERVER_FOLDER = PROJECT_ROOT / "server"

sys.path.append(str(SERVER_FOLDER))


from send_data import (
    ACCEL_AND_GYRO_UUID,
    DEVICE_NAMES,
    process_sensor_packet,
)

from prediction_buffer import add_reading, clear_all_buffers
from combined_predictor import predict_device
from prediction_voter import vote_prediction, clear_pending_votes

PROJECT_ROOT = Path(__file__).resolve().parent
SERVER_FOLDER = PROJECT_ROOT / "server"

sys.path.append(str(SERVER_FOLDER))


from send_data import (
    ACCEL_AND_GYRO_UUID,
    DEVICE_NAMES,
    process_sensor_packet,
)

from prediction_buffer import add_reading, clear_all_buffers
from combined_predictor import predict_device


PREDICTION_INTERVAL = 15


async def run_live_test():
    device_name = DEVICE_NAMES[0]

    print(f"Scanning for {device_name}...")

    devices = await BleakScanner.discover(timeout=10.0)

    device = None

    for found_device in devices:
        if found_device.name == device_name:
            device = found_device
            break

    if device is None:
        print(f"{device_name} was not found.")
        return

    clear_all_buffers()
    clear_pending_votes()

    async with BleakClient(device, timeout=20.0) as client:
        print(f"Connected to {device_name}.")

        characteristic = client.services.get_characteristic(
            ACCEL_AND_GYRO_UUID
        )

        if characteristic is None:
            print("Sensor characteristic was not found.")
            return

        def notification_handler(characteristic, data):
            try:
                reading = process_sensor_packet(
                    device_name,
                    data,
                )

                add_reading(
                    device_name,
                    reading,
                )

                sample_no = reading["sample_no"]

                # First prediction happens at 45 readings.
                # Then predict every new 15-reading block.
                if (
                    sample_no >= 45
                    and sample_no % PREDICTION_INTERVAL == 0
                ):
                    prediction = predict_device(device_name)

                    vote_result = vote_prediction(
                        device_name,
                        prediction,
                    )

                    print(
                        f"Sample {sample_no} | "
                        f"Rule: {prediction['rule_prediction']} | "
                        f"ML: {prediction['ml_prediction']} | "
                        f"Confidence: {prediction['ml_confidence']:.3f} | "
                        f"Status: {vote_result['decision_status']} | "
                        f"Final: {vote_result['final_prediction']}"
                    )

            except Exception as error:
                print("Prediction error:", error)

        await client.start_notify(
            characteristic,
            notification_handler,
        )

        print("Live prediction started. Press Ctrl+C to stop.")

        while client.is_connected:
            await asyncio.sleep(1)


if __name__ == "__main__":
    try:
        asyncio.run(run_live_test())

    except KeyboardInterrupt:
        print("\nLive prediction stopped.")