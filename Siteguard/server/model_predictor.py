"""Backend-only ML prediction for SiteGuard sensor readings."""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd


WINDOW_SIZE = 15
MINIMUM_READINGS = WINDOW_SIZE * 2
FULL_CONTEXT_READINGS = WINDOW_SIZE * 3

SENSOR_COLUMNS = [
    "accel_x",
    "accel_y",
    "accel_z",
    "gyro_x",
    "gyro_y",
    "gyro_z",
]

ACCELEROMETER_COLUMNS = [
    "accel_x",
    "accel_y",
    "accel_z",
]

COMPARED_VALUES = [
    "accmag_mean",
    "accmag_std",
    "gyromag_mean",
    "tilt_accel_x",
    "tilt_accel_y",
    "tilt_accel_z",
]


def acceleration_magnitude(readings):
    squared_total = (
        readings["accel_x"] ** 2
        + readings["accel_y"] ** 2
        + readings["accel_z"] ** 2
    )
    return np.sqrt(squared_total).to_numpy(dtype=float)


def rotation_magnitude(readings):
    squared_total = (
        readings["gyro_x"] ** 2
        + readings["gyro_y"] ** 2
        + readings["gyro_z"] ** 2
    )
    return np.sqrt(squared_total).to_numpy(dtype=float)


def axis_statistics(window):
    statistics = {}

    for column in SENSOR_COLUMNS:
        values = window[column].to_numpy(dtype=float)
        statistics[column + "_mean"] = values.mean()
        statistics[column + "_std"] = values.std()
        statistics[column + "_min"] = values.min()
        statistics[column + "_max"] = values.max()
        statistics[column + "_range"] = values.max() - values.min()
        statistics[column + "_energy"] = np.mean(values ** 2)

    return statistics


def magnitude_statistics(movement_strength, rotation_strength):
    return {
        "accmag_mean": movement_strength.mean(),
        "accmag_std": movement_strength.std(),
        "accmag_max": movement_strength.max(),
        "accmag_min": movement_strength.min(),
        "accmag_range": movement_strength.max() - movement_strength.min(),
        "accmag_mad": np.mean(
            np.abs(movement_strength - movement_strength.mean())
        ),
        "gyromag_mean": rotation_strength.mean(),
        "gyromag_std": rotation_strength.std(),
        "gyromag_max": rotation_strength.max(),
        "gyromag_min": rotation_strength.min(),
        "gyromag_range": rotation_strength.max() - rotation_strength.min(),
    }


def movement_change_statistics(movement_strength, rotation_strength):
    half = len(movement_strength) // 2
    movement_steps = np.diff(movement_strength)
    above_average = np.sign(
        movement_strength - movement_strength.mean()
    )

    return {
        "jerk_acc_std": movement_steps.std(),
        "jerk_acc_max": np.abs(movement_steps).max(),
        "accmag_half_diff": (
            movement_strength[half:].mean()
            - movement_strength[:half].mean()
        ),
        "gyromag_half_diff": (
            rotation_strength[half:].mean()
            - rotation_strength[:half].mean()
        ),
        "accmag_zerocross": float(
            np.sum(np.diff(above_average) != 0)
        ),
    }


def safe_divisor(value):
    if abs(value) < 1e-12:
        return 1e-12
    return value


def tilt_statistics(window, movement_strength):
    half = len(movement_strength) // 2
    average_strength = safe_divisor(movement_strength.mean())
    statistics = {}

    for column in ACCELEROMETER_COLUMNS:
        values = window[column].to_numpy(dtype=float)
        statistics["tilt_" + column] = (
            values.mean() / average_strength
        )
        statistics["halfdiff_" + column] = (
            values[half:].mean() - values[:half].mean()
        )

    return statistics


def neighbour_summary(readings, name_prefix):
    movement_strength = acceleration_magnitude(readings)
    rotation_strength = rotation_magnitude(readings)
    average_strength = movement_strength.mean()
    tilt_divisor = safe_divisor(average_strength)

    return {
        name_prefix + "accmag_mean": average_strength,
        name_prefix + "accmag_std": movement_strength.std(),
        name_prefix + "accmag_max": movement_strength.max(),
        name_prefix + "accmag_min": movement_strength.min(),
        name_prefix + "gyromag_mean": rotation_strength.mean(),
        name_prefix + "gyromag_std": rotation_strength.std(),
        name_prefix + "tilt_accel_x": (
            readings["accel_x"].mean() / tilt_divisor
        ),
        name_prefix + "tilt_accel_y": (
            readings["accel_y"].mean() / tilt_divisor
        ),
        name_prefix + "tilt_accel_z": (
            readings["accel_z"].mean() / tilt_divisor
        ),
    }


def extract_model_features(sensor_readings):
    if len(sensor_readings) < MINIMUM_READINGS:
        raise ValueError(
            f"At least {MINIMUM_READINGS} readings are required."
        )

    readings = pd.DataFrame(sensor_readings)

    required_columns = ["time"] + SENSOR_COLUMNS
    missing_columns = [
        column for column in required_columns
        if column not in readings.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}"
        )

    if len(readings) >= FULL_CONTEXT_READINGS:
        block = readings.iloc[-FULL_CONTEXT_READINGS:].reset_index(drop=True)
        window_start = WINDOW_SIZE
    else:
        block = readings.reset_index(drop=True)
        window_start = len(block) - MINIMUM_READINGS

    before_start = max(0, window_start - WINDOW_SIZE)
    readings_before = block.iloc[before_start:window_start]
    window = block.iloc[
        window_start:window_start + WINDOW_SIZE
    ]
    readings_after = block.iloc[
        window_start + WINDOW_SIZE:
        window_start + (WINDOW_SIZE * 2)
    ]

    if len(readings_before) == 0:
        readings_before = window.iloc[:1]

    if len(readings_after) == 0:
        readings_after = window.iloc[-1:]

    movement_strength = acceleration_magnitude(window)
    rotation_strength = rotation_magnitude(window)

    features = {}
    features.update(axis_statistics(window))
    features.update(
        magnitude_statistics(movement_strength, rotation_strength)
    )
    features.update(
        movement_change_statistics(
            movement_strength,
            rotation_strength,
        )
    )
    features.update(tilt_statistics(window, movement_strength))

    before_summary = neighbour_summary(readings_before, "pre_")
    after_summary = neighbour_summary(readings_after, "post_")
    features.update(before_summary)
    features.update(after_summary)

    for value_name in COMPARED_VALUES:
        features["dpost_" + value_name] = (
            after_summary["post_" + value_name]
            - features[value_name]
        )
        features["dpre_" + value_name] = (
            features[value_name]
            - before_summary["pre_" + value_name]
        )

    return features


def load_model(model_path):
    model = joblib.load(model_path)

    if hasattr(model, "n_jobs"):
        model.n_jobs = 1

    if not hasattr(model, "feature_names_in_"):
        raise ValueError(
            "The model does not contain its expected feature names."
        )

    return model


def predict_sensor_readings(model, sensor_readings):
    features = extract_model_features(sensor_readings)

    feature_names = list(model.feature_names_in_)

    missing_features = [
        feature_name
        for feature_name in feature_names
        if feature_name not in features
    ]

    if missing_features:
        raise ValueError(
            f"Could not calculate model features: {missing_features}"
        )

    feature_values = [
        features[feature_name]
        for feature_name in feature_names
    ]

    feature_table = pd.DataFrame(
        [feature_values],
        columns=feature_names,
    )

    probability_row = model.predict_proba(feature_table)[0]

    probabilities = {
        str(state): float(probability)
        for state, probability in zip(
            model.classes_,
            probability_row,
        )
    }

    predicted_state = max(
        probabilities,
        key=probabilities.get,
    )

    return {
        "predicted_state": predicted_state,
        "model_score": probabilities[predicted_state],
        "probabilities": probabilities,
    }


def run_self_check(model_path):
    model = load_model(model_path)

    test_readings = []

    for sample_number in range(FULL_CONTEXT_READINGS):
        test_readings.append(
            {
                "time": sample_number * 0.05,
                "accel_x": 0.0,
                "accel_y": 0.0,
                "accel_z": 1.0,
                "gyro_x": 0.0,
                "gyro_y": 0.0,
                "gyro_z": 0.0,
            }
        )

    result = predict_sensor_readings(model, test_readings)

    assert result["predicted_state"] in model.classes_
    assert len(result["probabilities"]) == len(model.classes_)

    print("Model self-check passed.")
    print("Prediction:", result["predicted_state"])
    print("Model score:", round(result["model_score"], 3))


if __name__ == "__main__":
    model_path = Path(__file__).resolve().parent.parent / "model" / "siteguard_model.joblib"
    run_self_check(model_path)
