"""Simple voting logic for SiteGuard Rule + ML predictions."""


MAX_FOLLOW_UP_ATTEMPTS = 2

# One pending disagreement per device.
pending_votes = {}


def vote_prediction(device_id, prediction):
    """Decide what to do with one Rule + ML prediction pair."""

    rule_prediction = prediction["rule_prediction"]
    ml_prediction = prediction["ml_prediction"]
    ml_confidence = prediction["ml_confidence"]

    # No unresolved disagreement for this device yet.
    if device_id not in pending_votes:

        # Immediate agreement.
        if rule_prediction == ml_prediction:
            return {
                "decision_status": "CONSENSUS",
                "final_prediction": rule_prediction,
                "rule_prediction": rule_prediction,
                "ml_prediction": ml_prediction,
                "ml_confidence": ml_confidence,
                "start_sample_no": prediction["start_sample_no"],
                "end_sample_no": prediction["end_sample_no"],
            }

        # Start waiting for follow-up predictions.
        pending_votes[device_id] = {
            "rule_prediction": rule_prediction,
            "ml_prediction": ml_prediction,
            "ml_confidence": ml_confidence,
            "start_sample_no": prediction["start_sample_no"],
            "end_sample_no": prediction["end_sample_no"],
            "follow_up_attempts": 0,
        }

        return {
            "decision_status": "PENDING",
            "final_prediction": None,
            "rule_prediction": rule_prediction,
            "ml_prediction": ml_prediction,
            "ml_confidence": ml_confidence,
        }

    # There is already an unresolved disagreement.
    pending = pending_votes[device_id]

    pending["follow_up_attempts"] += 1

    original_candidates = {
        pending["rule_prediction"],
        pending["ml_prediction"],
    }

    # A later agreement only counts if it matches
    # one of the ORIGINAL candidate predictions.
    if (
        rule_prediction == ml_prediction
        and rule_prediction in original_candidates
    ):
        result = {
            "decision_status": "CONSENSUS",
            "final_prediction": rule_prediction,
            "rule_prediction": pending["rule_prediction"],
            "ml_prediction": pending["ml_prediction"],
            "ml_confidence": pending["ml_confidence"],
            "start_sample_no": pending["start_sample_no"],
            "end_sample_no": pending["end_sample_no"],
        }
    
        del pending_votes[device_id]

        return result

    # No valid agreement after the allowed attempts.
    if pending["follow_up_attempts"] >= MAX_FOLLOW_UP_ATTEMPTS:
        result = {
            "decision_status": "ML_FALLBACK",
            "final_prediction": pending["ml_prediction"],
            "rule_prediction": pending["rule_prediction"],
            "ml_prediction": pending["ml_prediction"],
            "ml_confidence": pending["ml_confidence"],
            "start_sample_no": pending["start_sample_no"],
            "end_sample_no": pending["end_sample_no"],
        }

        del pending_votes[device_id]

        return result

    # Still waiting.
    return {
        "decision_status": "PENDING",
        "final_prediction": None,
        "rule_prediction": pending["rule_prediction"],
        "ml_prediction": pending["ml_prediction"],
        "ml_confidence": pending["ml_confidence"],
    }


def clear_pending_votes():
    """Clear all unresolved prediction disagreements."""

    pending_votes.clear()

if __name__ == "__main__":

    clear_pending_votes()

    # Test 1: Immediate agreement.
    result = vote_prediction(
        "Flowery",
        {
            "rule_prediction": "STATIONARY",
            "ml_prediction": "STATIONARY",
            "ml_confidence": 0.80,
            "start_sample_no": 100,
            "end_sample_no": 114,
        }
    )

    assert result["decision_status"] == "CONSENSUS"
    assert result["final_prediction"] == "STATIONARY"


    # Test 2: Disagreement followed by valid agreement.
    result = vote_prediction(
        "Kris",
        {
            "rule_prediction": "STF",
            "ml_prediction": "NEAR_MISS",
            "ml_confidence": 0.70,
            "start_sample_no": 200,
            "end_sample_no": 214,
        },
    )

    assert result["decision_status"] == "PENDING"

    result = vote_prediction(
        "Kris",
        {
            "rule_prediction": "STATIONARY",
            "ml_prediction": "STATIONARY",
            "ml_confidence": 0.90,
        },
    )

    assert result["decision_status"] == "PENDING"

    result = vote_prediction(
        "Kris",
        {
            "rule_prediction": "STF",
            "ml_prediction": "STF",
            "ml_confidence": 0.85,
        },
    )

    assert result["decision_status"] == "CONSENSUS"
    assert result["final_prediction"] == "STF"


    # Test 3: Disagreement that never resolves.
    result = vote_prediction(
        "Susie",
        {
            "rule_prediction": "STF",
            "ml_prediction": "NEAR_MISS",
            "ml_confidence": 0.75,
            "start_sample_no": 300,
            "end_sample_no": 314,
        },
    )

    assert result["decision_status"] == "PENDING"

    result = vote_prediction(
        "Susie",
        {
            "rule_prediction": "WALKING",
            "ml_prediction": "RUNNING",
            "ml_confidence": 0.60,
        },
    )

    assert result["decision_status"] == "PENDING"

    result = vote_prediction(
        "Susie",
        {
            "rule_prediction": "STATIONARY",
            "ml_prediction": "STATIONARY",
            "ml_confidence": 0.90,
        },
    )

    assert result["decision_status"] == "ML_FALLBACK"
    assert result["final_prediction"] == "NEAR_MISS"

    print("Voting self-check passed.")