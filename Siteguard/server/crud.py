from sqlalchemy import text


def save_reading(db, device_id, reading):

    query = text("""
        INSERT INTO sensor_data (
            device_id,
            sample_no,
            device_time,
            interval,
            accel_x,
            accel_y,
            accel_z,
            gyro_x,
            gyro_y,
            gyro_z
        )
        VALUES (
            :device_id,
            :sample_no,
            :device_time,
            :interval,
            :accel_x,
            :accel_y,
            :accel_z,
            :gyro_x,
            :gyro_y,
            :gyro_z
        )
    """)

    db.execute(
        query,
        {
            "device_id": device_id,
            "sample_no": reading["sample_no"],
            "device_time": reading["time"],
            "interval": reading["interval"],
            "accel_x": reading["accel_x"],
            "accel_y": reading["accel_y"],
            "accel_z": reading["accel_z"],
            "gyro_x": reading["gyro_x"],
            "gyro_y": reading["gyro_y"],
            "gyro_z": reading["gyro_z"],
        }
    )