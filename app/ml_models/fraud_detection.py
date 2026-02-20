import numpy as np
import os
import pickle

MODEL_PATH = os.path.join(os.path.dirname(__file__), "fraud_model.pkl")


def _rule_based_fraud_score(data: dict) -> float:
    """
    Rule-based fraud scoring when ML model is not trained yet.
    Returns a score between 0 (safe) and 1 (suspicious).
    """
    score = 0.0

    amount = data.get("amount", 0)
    hour = data.get("hour", 12)
    balance_before = data.get("balance_before", 0)
    txn_count_today = data.get("transaction_count_today", 0)

    # Large amount relative to balance
    if balance_before > 0 and amount / balance_before > 0.8:
        score += 0.3

    # Unusual hour (midnight to 5am)
    if 0 <= hour <= 5:
        score += 0.2

    # High transaction count today
    if txn_count_today > 10:
        score += 0.25

    # Extremely large amount
    if amount > 100000:
        score += 0.25

    return min(score, 1.0)


def predict_fraud(transaction_data: dict) -> dict:
    """
    Predict if a transaction is fraudulent.
    Returns dict with is_fraud (bool) and fraud_score (float).
    """
    try:
        if os.path.exists(MODEL_PATH):
            with open(MODEL_PATH, "rb") as f:
                model = pickle.load(f)

            features = np.array([[
                transaction_data.get("amount", 0),
                transaction_data.get("hour", 12),
                transaction_data.get("balance_before", 0),
                transaction_data.get("transaction_count_today", 0)
            ]])

            prediction = model.predict(features)[0]
            score = model.decision_function(features)[0]
            # Normalize score to 0-1 range
            normalized_score = max(0, min(1, (1 - score) / 2))

            return {
                "is_fraud": bool(prediction == -1),
                "fraud_score": round(float(normalized_score), 4),
                "model": "isolation_forest"
            }
        else:
            # Fallback to rule-based scoring
            score = _rule_based_fraud_score(transaction_data)
            return {
                "is_fraud": score >= 0.5,
                "fraud_score": round(score, 4),
                "model": "rule_based"
            }

    except Exception as e:
        # Safe fallback - don't block transaction on ML error
        return {
            "is_fraud": False,
            "fraud_score": 0.0,
            "model": "fallback_error"
        }
