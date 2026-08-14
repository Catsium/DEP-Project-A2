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
def save_prediction(db, device_id, prediction):

    query = text("""
        INSERT INTO predictions (
            device_id,
            rule_prediction,
            ml_prediction,
            ml_confidence,
            final_prediction,
            decision_status,
            start_sample_no,
            end_sample_no
        )
        VALUES (
            :device_id,
            :rule_prediction,
            :ml_prediction,
            :ml_confidence,
            :final_prediction,
            :decision_status,
            :start_sample_no,
            :end_sample_no
        )
    """)

    db.execute(
        query,
        {
            "device_id": device_id,
            "rule_prediction": prediction["rule_prediction"],
            "ml_prediction": prediction["ml_prediction"],
            "ml_confidence": prediction["ml_confidence"],
            "final_prediction": prediction["final_prediction"],
            "decision_status": prediction["decision_status"],
            "start_sample_no": prediction["start_sample_no"],
            "end_sample_no": prediction["end_sample_no"],
        }
    )