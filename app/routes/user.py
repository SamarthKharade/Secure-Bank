from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import mongo
from app.services.notification import send_transaction_alert_email, send_access_decision_email
from app.services.audit import log_action
from app.services.token import generate_permission_token
from bson import ObjectId
from datetime import datetime

user_bp = Blueprint("user", __name__)


def serialize_user(user):
    return {
        "user_id": str(user["_id"]),
        "name": user["name"],
        "email": user["email"],
        "phone": user["phone"],
        "account_number": user["account_number"],
        "balance": user["balance"],
        "is_active": user["is_active"],
        "created_at": str(user["created_at"])
    }


def serialize_transaction(txn):
    return {
        "transaction_id": str(txn["_id"]),
        "type": txn["type"],
        "amount": txn["amount"],
        "description": txn.get("description", ""),
        "balance_after": txn["balance_after"],
        "is_flagged": txn.get("is_flagged", False),
        "fraud_score": txn.get("fraud_score", 0),
        "timestamp": str(txn["timestamp"])
    }


@user_bp.route("/profile", methods=["GET"])
@jwt_required()
def get_profile():
    identity = get_jwt_identity()
    user = mongo.db.users.find_one({"_id": ObjectId(identity["user_id"])})
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(serialize_user(user)), 200


@user_bp.route("/dashboard", methods=["GET"])
@jwt_required()
def dashboard():
    identity = get_jwt_identity()
    user = mongo.db.users.find_one({"_id": ObjectId(identity["user_id"])})
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Recent 5 transactions
    transactions = list(mongo.db.transactions.find(
        {"user_id": str(user["_id"])},
        sort=[("timestamp", -1)],
        limit=5
    ))

    # Pending access requests
    pending_requests = list(mongo.db.access_requests.find({
        "user_id": str(user["_id"]),
        "status": "pending"
    }))

    return jsonify({
        "account": serialize_user(user),
        "recent_transactions": [serialize_transaction(t) for t in transactions],
        "pending_access_requests": len(pending_requests)
    }), 200


@user_bp.route("/deposit", methods=["POST"])
@jwt_required()
def deposit():
    identity = get_jwt_identity()
    data = request.get_json()

    amount = data.get("amount", 0)
    if amount <= 0:
        return jsonify({"error": "Amount must be greater than 0"}), 400
    if amount > 1000000:
        return jsonify({"error": "Maximum deposit limit is ₹10,00,000"}), 400

    user = mongo.db.users.find_one({"_id": ObjectId(identity["user_id"])})
    new_balance = user["balance"] + amount

    # Update balance
    mongo.db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"balance": new_balance}}
    )

    # Record transaction
    txn = {
        "user_id": str(user["_id"]),
        "type": "credit",
        "amount": amount,
        "description": data.get("description", "Deposit"),
        "balance_after": new_balance,
        "is_flagged": False,
        "fraud_score": 0.0,
        "timestamp": datetime.utcnow()
    }
    mongo.db.transactions.insert_one(txn)

    # Send alert email
    send_transaction_alert_email(user["email"], user["name"], "credit", amount, new_balance)

    log_action(str(user["_id"]), "user", "deposit", details={"amount": amount})

    return jsonify({
        "message": "Deposit successful",
        "amount": amount,
        "new_balance": new_balance
    }), 200


@user_bp.route("/withdraw", methods=["POST"])
@jwt_required()
def withdraw():
    identity = get_jwt_identity()
    data = request.get_json()

    amount = data.get("amount", 0)
    if amount <= 0:
        return jsonify({"error": "Amount must be greater than 0"}), 400

    user = mongo.db.users.find_one({"_id": ObjectId(identity["user_id"])})

    if user["balance"] < amount:
        return jsonify({"error": "Insufficient balance"}), 400

    new_balance = user["balance"] - amount

    # Check fraud before processing
    from app.ml_models.fraud_detection import predict_fraud
    fraud_result = predict_fraud({
        "amount": amount,
        "hour": datetime.utcnow().hour,
        "balance_before": user["balance"],
        "transaction_count_today": mongo.db.transactions.count_documents({
            "user_id": str(user["_id"]),
            "timestamp": {"$gte": datetime.utcnow().replace(hour=0, minute=0, second=0)}
        })
    })

    # Update balance
    mongo.db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"balance": new_balance}}
    )

    # Record transaction
    txn = {
        "user_id": str(user["_id"]),
        "type": "debit",
        "amount": amount,
        "description": data.get("description", "Withdrawal"),
        "balance_after": new_balance,
        "is_flagged": fraud_result["is_fraud"],
        "fraud_score": fraud_result["fraud_score"],
        "timestamp": datetime.utcnow()
    }
    mongo.db.transactions.insert_one(txn)

    send_transaction_alert_email(user["email"], user["name"], "debit", amount, new_balance)
    log_action(str(user["_id"]), "user", "withdrawal", details={
        "amount": amount,
        "fraud_flagged": fraud_result["is_fraud"]
    })

    response = {
        "message": "Withdrawal successful",
        "amount": amount,
        "new_balance": new_balance
    }

    if fraud_result["is_fraud"]:
        response["warning"] = "This transaction has been flagged for review"

    return jsonify(response), 200


@user_bp.route("/transfer", methods=["POST"])
@jwt_required()
def transfer():
    identity = get_jwt_identity()
    data = request.get_json()

    amount = data.get("amount", 0)
    to_account = data.get("to_account_number")

    if not to_account:
        return jsonify({"error": "Recipient account number required"}), 400
    if amount <= 0:
        return jsonify({"error": "Amount must be greater than 0"}), 400

    sender = mongo.db.users.find_one({"_id": ObjectId(identity["user_id"])})
    recipient = mongo.db.users.find_one({"account_number": to_account})

    if not recipient:
        return jsonify({"error": "Recipient account not found"}), 404
    if str(sender["_id"]) == str(recipient["_id"]):
        return jsonify({"error": "Cannot transfer to own account"}), 400
    if sender["balance"] < amount:
        return jsonify({"error": "Insufficient balance"}), 400

    sender_new_balance = sender["balance"] - amount
    recipient_new_balance = recipient["balance"] + amount

    # Debit sender
    mongo.db.users.update_one({"_id": sender["_id"]}, {"$set": {"balance": sender_new_balance}})
    # Credit recipient
    mongo.db.users.update_one({"_id": recipient["_id"]}, {"$set": {"balance": recipient_new_balance}})

    now = datetime.utcnow()

    # Sender transaction
    mongo.db.transactions.insert_one({
        "user_id": str(sender["_id"]),
        "type": "debit",
        "amount": amount,
        "description": f"Transfer to {recipient['account_number']} - {data.get('description', '')}",
        "balance_after": sender_new_balance,
        "related_account": to_account,
        "is_flagged": False,
        "fraud_score": 0.0,
        "timestamp": now
    })

    # Recipient transaction
    mongo.db.transactions.insert_one({
        "user_id": str(recipient["_id"]),
        "type": "credit",
        "amount": amount,
        "description": f"Transfer from {sender['account_number']} - {data.get('description', '')}",
        "balance_after": recipient_new_balance,
        "related_account": sender["account_number"],
        "is_flagged": False,
        "fraud_score": 0.0,
        "timestamp": now
    })

    send_transaction_alert_email(sender["email"], sender["name"], "debit", amount, sender_new_balance)
    send_transaction_alert_email(recipient["email"], recipient["name"], "credit", amount, recipient_new_balance)

    log_action(str(sender["_id"]), "user", "transfer", details={
        "amount": amount,
        "to_account": to_account
    })

    return jsonify({
        "message": "Transfer successful",
        "amount": amount,
        "to": recipient["name"],
        "new_balance": sender_new_balance
    }), 200


@user_bp.route("/transactions", methods=["GET"])
@jwt_required()
def get_transactions():
    identity = get_jwt_identity()
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 10))
    skip = (page - 1) * limit

    transactions = list(mongo.db.transactions.find(
        {"user_id": identity["user_id"]},
        sort=[("timestamp", -1)],
        skip=skip,
        limit=limit
    ))

    total = mongo.db.transactions.count_documents({"user_id": identity["user_id"]})

    return jsonify({
        "transactions": [serialize_transaction(t) for t in transactions],
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit
    }), 200


@user_bp.route("/access-requests", methods=["GET"])
@jwt_required()
def get_access_requests():
    """Get all pending access requests for the logged-in user."""
    identity = get_jwt_identity()
    requests = list(mongo.db.access_requests.find(
        {"user_id": identity["user_id"], "status": "pending"},
        sort=[("requested_at", -1)]
    ))

    result = []
    for r in requests:
        admin = mongo.db.users.find_one({"_id": ObjectId(r["admin_id"])})
        result.append({
            "request_id": str(r["_id"]),
            "admin_name": admin["name"] if admin else "Unknown",
            "reason": r["reason"],
            "requested_at": str(r["requested_at"]),
            "expires_at": str(r["expires_at"])
        })

    return jsonify({"access_requests": result}), 200


@user_bp.route("/grant-access/<request_id>", methods=["GET", "POST"])
def grant_access(request_id):
    """User grants access to admin. Works via link click or API."""
    req = mongo.db.access_requests.find_one({"_id": ObjectId(request_id)})

    if not req:
        return jsonify({"error": "Access request not found"}), 404
    if req["status"] != "pending":
        return jsonify({"error": f"Request already {req['status']}"}), 400

    # Check if expired
    if datetime.utcnow() > req["expires_at"]:
        mongo.db.access_requests.update_one(
            {"_id": ObjectId(request_id)},
            {"$set": {"status": "expired"}}
        )
        return jsonify({"error": "Access request has expired"}), 410

    # Generate permission token
    from app.services.token import generate_permission_token
    permission_token = generate_permission_token(req["admin_id"], req["user_id"], request_id)

    mongo.db.access_requests.update_one(
        {"_id": ObjectId(request_id)},
        {"$set": {
            "status": "granted",
            "permission_token": permission_token,
            "granted_at": datetime.utcnow()
        }}
    )

    # Notify admin
    admin = mongo.db.users.find_one({"_id": ObjectId(req["admin_id"])})
    user = mongo.db.users.find_one({"_id": ObjectId(req["user_id"])})

    if admin and user:
        send_access_decision_email(admin["email"], admin["name"], user["name"], "granted")

    log_action(req["user_id"], "user", "grant_admin_access", details={"request_id": request_id})

    return jsonify({
        "message": "Access granted successfully. Admin will be notified.",
        "expires_in": "30 minutes"
    }), 200


@user_bp.route("/deny-access/<request_id>", methods=["GET", "POST"])
def deny_access(request_id):
    """User denies admin access request."""
    req = mongo.db.access_requests.find_one({"_id": ObjectId(request_id)})

    if not req:
        return jsonify({"error": "Access request not found"}), 404
    if req["status"] != "pending":
        return jsonify({"error": f"Request already {req['status']}"}), 400

    mongo.db.access_requests.update_one(
        {"_id": ObjectId(request_id)},
        {"$set": {"status": "denied", "denied_at": datetime.utcnow()}}
    )

    admin = mongo.db.users.find_one({"_id": ObjectId(req["admin_id"])})
    user = mongo.db.users.find_one({"_id": ObjectId(req["user_id"])})

    if admin and user:
        send_access_decision_email(admin["email"], admin["name"], user["name"], "denied")

    log_action(req["user_id"], "user", "deny_admin_access", details={"request_id": request_id})

    return jsonify({"message": "Access denied. Admin has been notified."}), 200
