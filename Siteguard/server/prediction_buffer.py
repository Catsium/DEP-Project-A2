"""Keep recent sensor readings separately for each SiteGuard device."""

from collections import deque


BUFFER_SIZE = 45

device_buffers = {}


def add_reading(device_id, reading):
    """Add one sensor reading to a device's rolling buffer."""

    if device_id not in device_buffers:
        device_buffers[device_id] = deque(maxlen=BUFFER_SIZE)

    device_buffers[device_id].append(reading)


def get_readings(device_id):
    """Return the current readings stored for one device."""

    if device_id not in device_buffers:
        return []

    return list(device_buffers[device_id])


def has_enough_readings(device_id, minimum_readings=BUFFER_SIZE):
    """Check whether a device has enough readings for prediction."""

    return len(get_readings(device_id)) >= minimum_readings


def clear_buffer(device_id):
    """Clear readings for one device."""

    if device_id in device_buffers:
        del device_buffers[device_id]


def clear_all_buffers():
    """Clear readings for every device."""

    device_buffers.clear()

if __name__ == "__main__":

    for sample_number in range(50):
        reading = {
            "sample_no": sample_number,
        }

        add_reading("Flowery", reading)

    readings = get_readings("Flowery")

    print("Number of readings:", len(readings))
    print("First sample:", readings[0]["sample_no"])
    print("Last sample:", readings[-1]["sample_no"])
    print("Enough readings:", has_enough_readings("Flowery"))