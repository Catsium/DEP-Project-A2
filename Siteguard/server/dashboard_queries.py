from sqlalchemy import text

def get_incident_details(db, prediction_id):

    prediction_query = text("""
        SELECT
            id,
            device_id,
            session_id,
            rule_prediction,
            ml_prediction,
            ml_confidence,
            final_prediction,
            decision_status,
            start_sample_no,
            end_sample_no,
            created_at,
            COALESCE(review_status, 'OPEN')
                AS review_status,
            resolved_at

        FROM predictions

        WHERE id = :prediction_id

        LIMIT 1
    """)

    prediction = db.execute(
        prediction_query,
        {
            "prediction_id": prediction_id
        }
    ).mappings().first()


    if prediction is None:
        return None


    readings_query = text("""
        SELECT
            sample_no,
            device_time,
            interval,

            accel_x,
            accel_y,
            accel_z,

            gyro_x,
            gyro_y,
            gyro_z,

            received_at

        FROM sensor_data

        WHERE device_id = :device_id

        AND session_id
            IS NOT DISTINCT FROM
            :session_id

        AND sample_no BETWEEN
            :start_sample_no
            AND
            :end_sample_no

        ORDER BY sample_no
    """)


    readings = db.execute(
        readings_query,
        {
            "device_id":
                prediction["device_id"],

            "session_id":
                prediction["session_id"],

            "start_sample_no":
                prediction["start_sample_no"],

            "end_sample_no":
                prediction["end_sample_no"]
        }
    ).mappings().all()


    return {
        "prediction": dict(prediction),

        "readings": [
            dict(row)
            for row in readings
        ]
    }

def get_recent_safety_events(db):

    query = text("""
        SELECT
            id,
            device_id,
            session_id,
            rule_prediction,
            ml_prediction,
            ml_confidence,
            final_prediction,
            decision_status,
            start_sample_no,
            end_sample_no,
            created_at,
            COALESCE(review_status, 'OPEN')
                AS review_status,
            resolved_at

        FROM predictions
        WHERE final_prediction IN (
            'FFH',
            'STF',
            'NEAR_MISS'
        )
        ORDER BY created_at DESC
        LIMIT 10
    """)

    result = db.execute(query)

    rows = result.mappings().all()

    return [
        dict(row)
        for row in rows
    ]

def get_device_details(db, device_id):

    latest_sensor_query = text("""
        SELECT
            device_id,
            session_id,
            sample_no,
            received_at,

            CAST(
                EXTRACT(
                    EPOCH FROM (NOW() - received_at)
                )
                AS INTEGER
            ) AS seconds_since_last_seen,

            CASE
                WHEN NOW() - received_at < INTERVAL '10 seconds'
                THEN TRUE
                ELSE FALSE
            END AS online

        FROM sensor_data

        WHERE device_id = :device_id

        ORDER BY received_at DESC

        LIMIT 1
    """)

    latest_sensor = db.execute(
        latest_sensor_query,
        {"device_id": device_id}
    ).mappings().first()

    if latest_sensor is None:
        return None

    session_id = latest_sensor["session_id"]


    readings_query = text("""
        SELECT
            sample_no,
            device_time,
            interval,

            accel_x,
            accel_y,
            accel_z,

            gyro_x,
            gyro_y,
            gyro_z,

            received_at

        FROM sensor_data

        WHERE device_id = :device_id

        AND session_id IS NOT DISTINCT FROM :session_id

        ORDER BY sample_no DESC

        LIMIT 100
    """)

    readings = db.execute(
        readings_query,
        {
            "device_id": device_id,
            "session_id": session_id
        }
    ).mappings().all()

    readings = [
        dict(row)
        for row in readings
    ]

    # Oldest -> newest for graphs
    readings.reverse()


    predictions_query = text("""
        SELECT
            id,
            rule_prediction,
            ml_prediction,
            ml_confidence,
            final_prediction,
            decision_status,
            start_sample_no,
            end_sample_no,
            created_at

        FROM predictions

        WHERE device_id = :device_id

        AND session_id IS NOT DISTINCT FROM :session_id

        ORDER BY created_at DESC

        LIMIT 10
    """)

    predictions = db.execute(
        predictions_query,
        {
            "device_id": device_id,
            "session_id": session_id
        }
    ).mappings().all()

    predictions = [
        dict(row)
        for row in predictions
    ]


    latest_prediction = None

    if len(predictions) > 0:
        latest_prediction = predictions[0]


    return {
        "device": dict(latest_sensor),
        "latest_prediction": latest_prediction,
        "readings": readings,
        "predictions": predictions
    }

def get_dashboard_devices(db):

    query = text("""
        WITH configured_devices AS (
            SELECT *
            FROM (
                VALUES
                    ('Flowery'),
                    ('Catsium'),
                    ('Doggsium'),
                    ('Birdsium')
            ) AS devices(device_id)
        ),

        latest_sensor AS (
            SELECT DISTINCT ON (device_id)
                device_id,
                session_id,
                sample_no,
                received_at
            FROM sensor_data
            ORDER BY device_id, received_at DESC
        ),

        latest_prediction AS (
            SELECT DISTINCT ON (
                device_id,
                session_id
            )
                device_id,
                session_id,
                final_prediction,
                ml_confidence,
                decision_status,
                created_at
            FROM predictions
            ORDER BY
                device_id,
                session_id,
                created_at DESC
        )

        SELECT
            d.device_id,
            s.session_id,
            s.sample_no,
            s.received_at AS last_seen,

            CAST(
                EXTRACT(
                    EPOCH FROM (
                        NOW() - s.received_at
                    )
                )
                AS INTEGER
            ) AS seconds_since_last_seen,

            CASE
                WHEN s.received_at IS NULL
                THEN FALSE

                WHEN NOW() - s.received_at
                     < INTERVAL '10 seconds'
                THEN TRUE

                ELSE FALSE
            END AS online,

            p.final_prediction,
            p.ml_confidence,
            p.decision_status,
            p.created_at AS prediction_time

        FROM configured_devices d

        LEFT JOIN latest_sensor s
            ON d.device_id = s.device_id

        LEFT JOIN latest_prediction p
            ON s.device_id = p.device_id

            AND s.session_id
                IS NOT DISTINCT FROM
                p.session_id

        ORDER BY d.device_id
        """)

    result = db.execute(query)

    return [
        dict(row)
        for row in result.mappings().all()
    ]

def get_dashboard_insights(
    db,
    device="All",
    event="All",
    days=7
):

    query = text("""
        SELECT
            id,
            device_id,
            final_prediction,
            created_at

        FROM predictions

        WHERE final_prediction IN (
            'FFH',
            'STF',
            'NEAR_MISS'
        )

        AND device_id IN (
            'Flowery',
            'Catsium',
            'Doggsium',
            'Birdsium'
        )

        AND (
            :device = 'All'
            OR device_id = :device
        )

        AND (
            :event = 'All'
            OR final_prediction = :event
        )

        AND (
            created_at
            AT TIME ZONE 'Asia/Singapore'
        )::date
        >=
        (
            NOW()
            AT TIME ZONE 'Asia/Singapore'
        )::date
        -
        (
            CAST(:days AS INTEGER) - 1
        )

        ORDER BY created_at ASC
    """)

    result = db.execute(
        query,
        {
            "device": device,
            "event": event,
            "days": days
        }
    )

    return [
        dict(row)
        for row in result.mappings().all()
    ]

def get_dashboard_summary(db):

    # -----------------------------
    # 1. Count currently active Nessos
    # -----------------------------
    active_query = text("""
        WITH latest_sensor AS (
            SELECT DISTINCT ON (device_id)
                device_id,
                received_at
            FROM sensor_data
            WHERE device_id IN (
                'Flowery',
                'Catsium',
                'Doggsium',
                'Birdsium'
            )
            ORDER BY device_id, received_at DESC
        )

        SELECT COUNT(*) AS active_nessos

        FROM latest_sensor

        WHERE NOW() - received_at
              < INTERVAL '10 seconds'
    """)

    active_result = db.execute(
        active_query
    ).mappings().first()


    # -----------------------------
    # 2. Count today's safety events
    # Singapore time
    # -----------------------------
    counts_query = text("""
        SELECT

            COUNT(*) FILTER (
                WHERE final_prediction IN (
                    'FFH',
                    'STF'
                )
            ) AS falls_today,

            COUNT(*) FILTER (
                WHERE final_prediction = 'NEAR_MISS'
            ) AS near_misses_today,

            COUNT(*) AS total_events_today

        FROM predictions

        WHERE final_prediction IN (
            'FFH',
            'STF',
            'NEAR_MISS'
        )

        AND device_id IN (
            'Flowery',
            'Catsium',
            'Doggsium',
            'Birdsium'
        )

        AND (
            created_at
            AT TIME ZONE 'Asia/Singapore'
        )::date
        =
        (
            NOW()
            AT TIME ZONE 'Asia/Singapore'
        )::date
    """)

    counts = db.execute(
        counts_query
    ).mappings().first()


    # -----------------------------
    # 3. Get latest safety event
    # -----------------------------
    latest_event_query = text("""
        SELECT
            id,
            device_id,
            rule_prediction,
            ml_prediction,
            ml_confidence,
            final_prediction,
            decision_status,
            created_at,
            COALESCE(review_status, 'OPEN')
                AS review_status,
            resolved_at

        FROM predictions

        WHERE final_prediction IN (
            'FFH',
            'STF',
            'NEAR_MISS'
        )

        AND device_id IN (
            'Flowery',
            'Catsium',
            'Doggsium',
            'Birdsium'
        )

        ORDER BY created_at DESC

        LIMIT 1
    """)

    latest_event = db.execute(
        latest_event_query
    ).mappings().first()


    return {
        "active_nessos":
            int(active_result["active_nessos"]),

        "falls_today":
            int(counts["falls_today"]),

        "near_misses_today":
            int(counts["near_misses_today"]),

        "total_events_today":
            int(counts["total_events_today"]),

        "latest_event":
            dict(latest_event)
            if latest_event
            else None
    }

def resolve_incident(db, prediction_id):

    query = text("""
        UPDATE predictions

        SET
            review_status = 'RESOLVED',
            resolved_at = NOW()

        WHERE id = :prediction_id

        AND final_prediction IN (
            'FFH',
            'STF',
            'NEAR_MISS'
        )

        RETURNING
            id,
            device_id,
            final_prediction,
            review_status,
            resolved_at
    """)

    result = db.execute(
        query,
        {
            "prediction_id": prediction_id
        }
    )

    return result.mappings().first()