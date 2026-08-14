from database import SessionLocal
from crud import save_prediction
from database import SessionLocal
from crud import save_prediction

print("Starting test...")

print("Creating database session...")
db = SessionLocal()

try:
    print("Trying database insert...")

    test_prediction = {
        "rule_prediction": "STATIONARY",
        "ml_prediction": "STATIONARY",
        "ml_confidence": 0.95,
        "final_prediction": "STATIONARY",
        "decision_status": "CONSENSUS",
        "start_sample_no": 100,
        "end_sample_no": 114,
    }

    save_prediction(
        db,
        "Flowery",
        test_prediction,
    )

    print("Committing...")
    db.commit()

    print("Prediction saved successfully.")

except Exception as error:
    db.rollback()
    print("Prediction save failed:", error)

finally:
    db.close()
    print("Database session closed.")

db = SessionLocal()

try:
    test_prediction = {
        "rule_prediction": "STATIONARY",
        "ml_prediction": "STATIONARY",
        "ml_confidence": 0.95,
        "final_prediction": "STATIONARY",
        "decision_status": "CONSENSUS",
        "start_sample_no": 100,
        "end_sample_no": 114,
    }

    save_prediction(
        db,
        "Flowery",
        test_prediction,
    )

    db.commit()

    print("Prediction saved successfully.")

except Exception as error:
    db.rollback()
    print("Prediction save failed:", error)

finally:
    db.close()