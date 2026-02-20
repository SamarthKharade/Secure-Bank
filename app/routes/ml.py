from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import mongo
from app.ml_models.fraud_detection import predict_fraud
from app.ml_models.loan_eligibility import predict_loan_eligibility
from app.ml_models.spending_analysis import analyze_spending
from bson import ObjectId
from datetime import datetime, timedelta

ml_bp = Blueprint("ml", __name__)


@ml_bp.route("/fraud-check", methods=["POST"])
@jwt_required()
def fraud_check():
    """Check if a transaction looks fraudulent."""
    data = request.get_json()
    identity = get_jwt_identity()

    # Get today's transaction count for this user
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    txn_count_today = mongo.db.transactions.count_documents({
        "user_id": identity["user_id"],
        "timestamp": {"$gte": today_start}
    })

    user = mongo.db.users.find_one({"_id": ObjectId(identity["user_id"])})

    transaction_data = {
        "amount": data.get("amount", 0),
        "hour": datetime.utcnow().hour,
        "balance_before": user["balance"] if user else 0,
        "transaction_count_today": txn_count_today
    }

    result = predict_fraud(transaction_data)

    return jsonify({
        "amount": data.get("amount"),
        "is_fraud": result["is_fraud"],
        "fraud_score": result["fraud_score"],
        "risk_level": "HIGH" if result["fraud_score"] >= 0.7 else "MEDIUM" if result["fraud_score"] >= 0.4 else "LOW",
        "model_used": result["model"]
    }), 200


@ml_bp.route("/loan-eligibility", methods=["POST"])
@jwt_required()
def loan_eligibility():
    """Predict loan eligibility for the logged-in user."""
    identity = get_jwt_identity()
    data = request.get_json()

    requested_amount = data.get("requested_amount", 0)
    if requested_amount <= 0:
        return jsonify({"error": "Requested amount must be greater than 0"}), 400

    user = mongo.db.users.find_one({"_id": ObjectId(identity["user_id"])})
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Calculate features from account history
    all_transactions = list(mongo.db.transactions.find({"user_id": identity["user_id"]}))

    # Average balance (approximate from transaction history)
    balances = [t["balance_after"] for t in all_transactions if "balance_after" in t]
    avg_balance = sum(balances) / len(balances) if balances else user["balance"]

    # Account age in days
    account_age = (datetime.utcnow() - user["created_at"]).days

    # Monthly transaction count (last 30 days)
    month_ago = datetime.utcnow() - timedelta(days=30)
    monthly_txn_count = mongo.db.transactions.count_documents({
        "user_id": identity["user_id"],
        "timestamp": {"$gte": month_ago}
    })

    applicant_data = {
        "average_balance": avg_balance,
        "account_age_days": account_age,
        "monthly_transaction_count": monthly_txn_count,
        "requested_amount": requested_amount
    }

    result = predict_loan_eligibility(applicant_data)

    return jsonify({
        "applicant": user["name"],
        "requested_amount": requested_amount,
        "eligible": result["eligible"],
        "eligibility_score": result["score"],
        "confidence": result["confidence"],
        "reasons": result["reasons"],
        "model_used": result["model"],
        "recommendation": "Approved for review" if result["eligible"] else "Not eligible at this time"
    }), 200


@ml_bp.route("/spending-analysis", methods=["GET"])
@jwt_required()
def spending_analysis():
    """Get spending category analysis for the user."""
    identity = get_jwt_identity()

    # Last 90 days
    days = int(request.args.get("days", 90))
    since = datetime.utcnow() - timedelta(days=days)

    transactions = list(mongo.db.transactions.find({
        "user_id": identity["user_id"],
        "timestamp": {"$gte": since}
    }))

    if not transactions:
        return jsonify({"message": "No transactions found for the selected period"}), 200

    result = analyze_spending(transactions)

    return jsonify({
        "period_days": days,
        "analysis": result
    }), 200


@ml_bp.route("/credit-score", methods=["GET"])
@jwt_required()
def credit_score():
    """Calculate a simulated credit score (300-900) based on account behavior."""
    identity = get_jwt_identity()

    user = mongo.db.users.find_one({"_id": ObjectId(identity["user_id"])})
    if not user:
        return jsonify({"error": "User not found"}), 404

    all_transactions = list(mongo.db.transactions.find({"user_id": identity["user_id"]}))

    score = 300  # Base score
    factors = []

    # 1. Account age (up to 100 points)
    account_age_days = (datetime.utcnow() - user["created_at"]).days
    age_score = min(100, account_age_days // 3)
    score += age_score
    factors.append({"factor": "Account Age", "points": age_score, "max": 100})

    # 2. Balance consistency (up to 150 points)
    if all_transactions:
        balances = [t["balance_after"] for t in all_transactions]
        avg_balance = sum(balances) / len(balances)
        min_balance = min(balances)
        balance_score = min(150, int(avg_balance / 1000) * 10) if avg_balance > 0 else 0
        score += balance_score
        factors.append({"factor": "Average Balance", "points": balance_score, "max": 150})
    else:
        factors.append({"factor": "Average Balance", "points": 0, "max": 150})

    # 3. Transaction frequency (up to 150 points)
    month_ago = datetime.utcnow() - timedelta(days=30)
    monthly_count = sum(1 for t in all_transactions if t["timestamp"] >= month_ago)
    freq_score = min(150, monthly_count * 10)
    score += freq_score
    factors.append({"factor": "Transaction Activity", "points": freq_score, "max": 150})

    # 4. No fraud flags (up to 200 points)
    flagged_count = sum(1 for t in all_transactions if t.get("is_flagged"))
    fraud_score = max(0, 200 - flagged_count * 50)
    score += fraud_score
    factors.append({"factor": "Clean Transaction History", "points": fraud_score, "max": 200})

    final_score = min(900, score)

    if final_score >= 750:
        rating = "Excellent"
        color = "green"
    elif final_score >= 650:
        rating = "Good"
        color = "blue"
    elif final_score >= 550:
        rating = "Fair"
        color = "yellow"
    else:
        rating = "Poor"
        color = "red"

    return jsonify({
        "credit_score": final_score,
        "rating": rating,
        "color": color,
        "factors": factors,
        "note": "This is a simulated credit score for demonstration purposes only."
    }), 200
