# Sensor Data
CREATE TABLE sensor_data (
    id BIGSERIAL PRIMARY KEY,

    device_id TEXT NOT NULL,
    sample_no INTEGER NOT NULL,

    device_time DOUBLE PRECISION,
    interval DOUBLE PRECISION,

    accel_x DOUBLE PRECISION,
    accel_y DOUBLE PRECISION,
    accel_z DOUBLE PRECISION,

    gyro_x DOUBLE PRECISION,
    gyro_y DOUBLE PRECISION,
    gyro_z DOUBLE PRECISION,

    received_at TIMESTAMPTZ DEFAULT NOW()
);

# Prediction Database
CREATE TABLE predictions (
    id BIGSERIAL PRIMARY KEY,

    device_id TEXT NOT NULL,

    rule_prediction TEXT NOT NULL,
    ml_prediction TEXT NOT NULL,
    ml_confidence DOUBLE PRECISION NOT NULL,

    final_prediction TEXT NOT NULL,
    decision_status TEXT NOT NULL,

    start_sample_no INTEGER NOT NULL,
    end_sample_no INTEGER NOT NULL,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

# Duplicate Checking
ALTER TABLE predictions
ADD COLUMN IF NOT EXISTS review_status TEXT;

ALTER TABLE predictions
ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ;

# hi gpt im honestly not sure tell me
ALTER TABLE sensor_data
ADD COLUMN IF NOT EXISTS session_id TEXT;

ALTER TABLE predictions
ADD COLUMN IF NOT EXISTS session_id TEXT;


CREATE UNIQUE INDEX IF NOT EXISTS sensor_data_unique_session_sample
ON sensor_data (
    device_id,
    session_id,
    sample_no
)
WHERE session_id IS NOT NULL;


CREATE UNIQUE INDEX IF NOT EXISTS predictions_unique_session_window
ON predictions (
    device_id,
    session_id,
    start_sample_no,
    end_sample_no
)
WHERE session_id IS NOT NULL;

## and this asw i think its checks
SELECT
    COUNT(*) AS prediction_count,
    MIN(start_sample_no) AS first_prediction_start,
    MAX(end_sample_no) AS last_prediction_end
FROM predictions
WHERE device_id = 'Flowery'
  AND session_id = '20260814_182635_439610';