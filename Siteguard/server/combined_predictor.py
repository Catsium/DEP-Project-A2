"""Run the SiteGuard rule and ML predictors on the same sensor event."""

import sys
from pathlib import Path


# Allow server code to import from the project-level algorithm folder.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))


from algorithm.detection_algorithm import classify_sensor_window
from model_predictor import load_model, predict_sensor_readings
from prediction_buffer import get_readings, has_enough_readings


WINDOW_SIZE = 15
FULL_CONTEXT_READINGS = 45

MODEL_PATH = (
    PROJECT_ROOT
    / "model"
    / "siteguard_model.joblib"
)

model = load_model(MODEL_PATH)


def predict_device(device_id):
    """Run Rule + ML predictions for one device."""

    if not has_enough_readings(device_id, FULL_CONTEXT_READINGS):
        return None

    sensor_readings = get_readings(device_id)

    # Use exactly the latest 45 readings.
    context_readings = sensor_readings[-FULL_CONTEXT_READINGS:]

    # The ML model treats the middle 15 as the target event.
    target_window = context_readings[
        WINDOW_SIZE:WINDOW_SIZE * 2
    ]
    start_sample_no = target_window[0]["sample_no"]
    end_sample_no = target_window[-1]["sample_no"]

    rule_result = classify_sensor_window(target_window)

    if rule_result["status"] != "OK":
        raise ValueError(rule_result["reason"])

    ml_result = predict_sensor_readings(
        model,
        context_readings
    )

    return {
        "rule_prediction": rule_result["subtype"],
        "ml_prediction": ml_result["predicted_state"],
        "ml_confidence": ml_result["model_score"],
        "start_sample_no": start_sample_no,
        "end_sample_no": end_sample_no,
    }

if __name__ == "__main__":

    from prediction_buffer import add_reading, clear_all_buffers

    clear_all_buffers()

    for sample_number in range(45):
        reading = {
            "sample_no": sample_number,
            "time": sample_number * 0.05,
            "interval": 50.0,
            "accel_x": 0.0,
            "accel_y": 0.0,
            "accel_z": 1.0,
            "gyro_x": 0.0,
            "gyro_y": 0.0,
            "gyro_z": 0.0,
        }

        add_reading("Flowery", reading)

    result = predict_device("Flowery")

    print(result)