"""Independent current-window detector for SiteGuard sensor readings."""

import math
import statistics



WINDOW_SIZE = 15
MAX_INTERVAL_MS = 500.0

FALL_IMPACT_THRESHOLD = 1.90
FFH_IMPACT_THRESHOLD = 2.70

NEAR_MISS_IMPACT_THRESHOLD = 1.25
NEAR_MISS_FREEFALL_THRESHOLD = 0.70
NEAR_MISS_ROTATION_THRESHOLD = 120.0

GET_UP_ROTATION_THRESHOLD = 110.0
GET_UP_ORIENTATION_THRESHOLD = 20.0

STATIONARY_MOTION_THRESHOLD = 0.12
RUNNING_MOTION_THRESHOLD = 0.40

SENSOR_COLUMNS = [
    "accel_x",
    "accel_y",
    "accel_z",
    "gyro_x",
    "gyro_y",
    "gyro_z",
]


def calculate_vector_magnitude(x_value, y_value, z_value):
    return math.sqrt(x_value**2 + y_value**2 + z_value**2)


def calculate_average_vector(vectors):
    average_x = statistics.mean(vector[0] for vector in vectors)
    average_y = statistics.mean(vector[1] for vector in vectors)
    average_z = statistics.mean(vector[2] for vector in vectors)
    return (average_x, average_y, average_z)


def calculate_angle_between_vectors(first_vector, second_vector):
    first_magnitude = calculate_vector_magnitude(*first_vector)
    second_magnitude = calculate_vector_magnitude(*second_vector)

    if first_magnitude == 0 or second_magnitude == 0:
        return 0.0

    dot_product = sum(
        first_value * second_value
        for first_value, second_value in zip(first_vector, second_vector)
    )
    cosine_value = dot_product / (first_magnitude * second_magnitude)
    cosine_value = max(-1.0, min(1.0, cosine_value))
    return math.degrees(math.acos(cosine_value))


def calculate_orientation_change(acceleration_vectors, impact_index):
    before_start = max(0, impact_index - 3)
    after_end = min(WINDOW_SIZE, impact_index + 4)

    before_vectors = acceleration_vectors[before_start : impact_index + 1]
    after_vectors = acceleration_vectors[impact_index:after_end]

    before_average = calculate_average_vector(before_vectors)
    after_average = calculate_average_vector(after_vectors)
    return calculate_angle_between_vectors(before_average, after_average)


def insufficient_data_result(reason):
    return {
        "status": "INSUFFICIENT_DATA",
        "reason": reason,
        "category": None,
        "subtype": None,
        "feature_values": {},
    }


def classify_sensor_window(sensor_readings):
    """
    Classify the latest 15 readings without using the ML model.

    Each reading uses interval, accel_x, accel_y, accel_z, gyro_x, gyro_y,
    and gyro_z. Extra fields such as time are allowed and ignored.
    """

    if not isinstance(sensor_readings, (list, tuple)):
        return insufficient_data_result("Sensor readings must be a list or tuple.")

    if len(sensor_readings) < WINDOW_SIZE:
        return insufficient_data_result("At least 15 sensor readings are required.")

    current_window = sensor_readings[-WINDOW_SIZE:]
    acceleration_vectors = []
    acceleration_magnitudes = []
    gyroscope_magnitudes = []
    interval_seconds = [None]

    for reading_number, reading in enumerate(current_window):
        if not isinstance(reading, dict):
            return insufficient_data_result("Every sensor reading must be a dictionary.")

        try:
            sensor_values = []
            for column_name in SENSOR_COLUMNS:
                sensor_value = float(reading[column_name])
                if not math.isfinite(sensor_value):
                    raise ValueError
                sensor_values.append(sensor_value)
        except (KeyError, TypeError, ValueError):
            return insufficient_data_result(
                "A sensor value is missing or is not a finite number."
            )

        accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z = sensor_values
        acceleration_vector = (accel_x, accel_y, accel_z)
        acceleration_vectors.append(acceleration_vector)
        acceleration_magnitudes.append(
            calculate_vector_magnitude(accel_x, accel_y, accel_z)
        )
        gyroscope_magnitudes.append(
            calculate_vector_magnitude(gyro_x, gyro_y, gyro_z)
        )

        # The first interval connects to a reading outside the current window.
        if reading_number > 0:
            try:
                interval_ms = float(reading["interval"])
            except (KeyError, TypeError, ValueError):
                return insufficient_data_result(
                    "An interval inside the current window is missing or invalid."
                )

            if not math.isfinite(interval_ms) or interval_ms <= 0:
                return insufficient_data_result(
                    "An interval inside the current window is missing or invalid."
                )

            if interval_ms > MAX_INTERVAL_MS:
                return insufficient_data_result(
                    "A sensor gap inside the current window is greater than 500 ms."
                )

            interval_seconds.append(interval_ms / 1000.0)

    impact = max(acceleration_magnitudes)
    freefall = min(acceleration_magnitudes)
    motion_standard_deviation = statistics.pstdev(acceleration_magnitudes)

    rotation = 0.0
    for reading_number in range(1, WINDOW_SIZE):
        rotation += (
            gyroscope_magnitudes[reading_number]
            * interval_seconds[reading_number]
        )

    impact_index = acceleration_magnitudes.index(impact)
    orientation_change = calculate_orientation_change(
        acceleration_vectors,
        impact_index,
    )

    feature_values = {
        "impact": impact,
        "freefall": freefall,
        "motion_standard_deviation": motion_standard_deviation,
        "rotation": rotation,
        "orientation_change": orientation_change,
    }

    if impact >= FALL_IMPACT_THRESHOLD:
        fall_subtype = "FFH" if impact >= FFH_IMPACT_THRESHOLD else "STF"
        return {
            "status": "OK",
            "reason": None,
            "category": "FALL",
            "subtype": fall_subtype,
            "feature_values": feature_values,
        }

    if (
        impact >= NEAR_MISS_IMPACT_THRESHOLD
        and freefall <= NEAR_MISS_FREEFALL_THRESHOLD
        and rotation >= NEAR_MISS_ROTATION_THRESHOLD
    ):
        return {
            "status": "OK",
            "reason": None,
            "category": "NEAR_MISS",
            "subtype": "NEAR_MISS",
            "feature_values": feature_values,
        }

    if (
        rotation >= GET_UP_ROTATION_THRESHOLD
        and orientation_change >= GET_UP_ORIENTATION_THRESHOLD
    ):
        return {
            "status": "OK",
            "reason": None,
            "category": "NON_FALL",
            "subtype": "GET_UP",
            "feature_values": feature_values,
        }

    if motion_standard_deviation < STATIONARY_MOTION_THRESHOLD:
        non_fall_subtype = "STATIONARY"
    elif motion_standard_deviation >= RUNNING_MOTION_THRESHOLD:
        non_fall_subtype = "RUNNING"
    else:
        non_fall_subtype = "WALKING"

    return {
        "status": "OK",
        "reason": None,
        "category": "NON_FALL",
        "subtype": non_fall_subtype,
        "feature_values": feature_values,
    }


def create_test_window(acceleration_magnitudes, gyro_z=0.0):
    test_window = []
    for acceleration_magnitude in acceleration_magnitudes:
        test_window.append(
            {
                "interval": 100.0,
                "accel_x": 0.0,
                "accel_y": 0.0,
                "accel_z": acceleration_magnitude,
                "gyro_x": 0.0,
                "gyro_y": 0.0,
                "gyro_z": gyro_z,
            }
        )
    return test_window


def run_self_check():
    stationary_window = create_test_window([1.0] * WINDOW_SIZE)
    assert classify_sensor_window(stationary_window)["subtype"] == "STATIONARY"

    walking_window = create_test_window([0.9, 1.3] * 7 + [0.9])
    assert classify_sensor_window(walking_window)["subtype"] == "WALKING"

    running_window = create_test_window([0.8, 1.7] * 7 + [0.8])
    assert classify_sensor_window(running_window)["subtype"] == "RUNNING"

    walking_dip_window = create_test_window([1.0] * WINDOW_SIZE)
    walking_dip_window[6]["accel_z"] = 0.6
    walking_dip_window[7]["accel_z"] = 1.3
    assert classify_sensor_window(walking_dip_window)["subtype"] == "WALKING"

    near_miss_window = create_test_window([1.0] * WINDOW_SIZE, gyro_z=100.0)
    near_miss_window[6]["accel_z"] = 0.6
    near_miss_window[7]["accel_z"] = 1.3
    assert classify_sensor_window(near_miss_window)["category"] == "NEAR_MISS"

    stf_window = create_test_window([1.0] * WINDOW_SIZE)
    stf_window[7]["accel_z"] = 2.0
    assert classify_sensor_window(stf_window)["subtype"] == "STF"

    ffh_window = create_test_window([1.0] * WINDOW_SIZE)
    ffh_window[7]["accel_z"] = 3.0
    assert classify_sensor_window(ffh_window)["subtype"] == "FFH"

    get_up_window = create_test_window([1.0] * WINDOW_SIZE, gyro_z=100.0)
    for reading_number in range(8, WINDOW_SIZE):
        get_up_window[reading_number]["accel_x"] = 1.0
        get_up_window[reading_number]["accel_z"] = 0.0
    get_up_window[7]["accel_z"] = 1.1
    assert classify_sensor_window(get_up_window)["subtype"] == "GET_UP"

    gap_window = create_test_window([1.0] * WINDOW_SIZE)
    gap_window[5]["interval"] = 600.0
    assert classify_sensor_window(gap_window)["status"] == "INSUFFICIENT_DATA"

    invalid_window = create_test_window([1.0] * WINDOW_SIZE)
    invalid_window[5].pop("gyro_z")
    assert classify_sensor_window(invalid_window)["status"] == "INSUFFICIENT_DATA"

    print("Self-check passed for all detection branches.")


if __name__ == "__main__":
    run_self_check()
