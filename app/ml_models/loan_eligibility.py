import numpy as np
import os
import pickle

MODEL_PATH = os.path.join(os.path.dirname(__file__), "loan_model.pkl")


def _rule_based_loan_score(data: dict) -> dict:
    """Rule-based loan eligibility when ML model not trained."""
    score = 0
    reasons = []

    balance = data.get("average_balance", 0)
    account_age_days = data.get("account_age_days", 0)
    txn_count = data.get("monthly_transaction_count", 0)
    loan_amount = data.get("requested_amount", 0)

    # Balance check
    if balance >= loan_amount * 0.3:
        score += 30
    else:
        reasons.append("Low average balance relative to loan amount")

    # Account age check
    if account_age_days >= 180:
        score += 25
    elif account_age_days >= 90:
        score += 15
        reasons.append("Account is relatively new")
    else:
        reasons.append("Account too new (less than 90 days)")

    # Transaction activity
    if txn_count >= 10:
        score += 25
    elif txn_count >= 5:
        score += 15
        reasons.append("Low transaction activity")
    else:
        reasons.append("Very low transaction activity")

    # Loan amount vs balance ratio
    if loan_amount <= balance * 3:
        score += 20
    elif loan_amount <= balance * 6:
        score += 10
        reasons.append("High loan-to-balance ratio")
    else:
        reasons.append("Loan amount too high relative to balance")

    eligible = score >= 60

    return {
        "eligible": eligible,
        "score": score,
        "confidence": round(score / 100, 2),
        "reasons": reasons if not eligible else ["Good account history", "Sufficient balance"],
        "model": "rule_based"
    }


def predict_loan_eligibility(applicant_data: dict) -> dict:
    """
    Predict loan eligibility for a user.
    Returns eligibility status, score, and reasons.
    """
    try:
        if os.path.exists(MODEL_PATH):
            with open(MODEL_PATH, "rb") as f:
                model = pickle.load(f)

            features = np.array([[
                applicant_data.get("average_balance", 0),
                applicant_data.get("account_age_days", 0),
                applicant_data.get("monthly_transaction_count", 0),
                applicant_data.get("requested_amount", 0)
            ]])

            prediction = model.predict(features)[0]
            proba = model.predict_proba(features)[0]

            return {
                "eligible": bool(prediction == 1),
                "score": int(proba[1] * 100),
                "confidence": round(float(proba[1]), 2),
                "reasons": [],
                "model": "logistic_regression"
            }
        else:
            return _rule_based_loan_score(applicant_data)

    except Exception:
        return _rule_based_loan_score(applicant_data)
