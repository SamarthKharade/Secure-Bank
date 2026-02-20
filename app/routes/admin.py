from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import mongo
from app.services.notification import send_access_request_email
from app.services.token import verify_permission_token
from app.services.audit import log_action
from bson import ObjectId
from datetime import datetime, timedelta
from functools import wraps

admin_bp = Blueprint("admin", __name__)


def admin_required(fn):
    """Decorator to ensure only admins can access the route."""
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        identity = get_jwt_identity()
        if identity.get("role") != "admin":
            return jsonify({"error": "Admin access required"}), 403
        return fn(*args, **kwargs)
    return wrapper


@admin_bp.route("/dashboard", methods=["GET"])
@admin_required
def admin_dashboard():
    """Admin overview dashboard."""
    total_users = mongo.db.users.count_documents({"role": "user"})
    total_transactions = mongo.db.transactions.count_documents({})
    flagged_transactions = mongo.db.transactions.count_documents({"is_flagged": True})
    pending_requests = mongo.db.access_requests.count_documents({"status": "pending"})

    # Today's transactions
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_transactions = mongo.db.transactions.count_documents({
        "timestamp": {"$gte": today_start}
    })

    return jsonify({
        "total_users": total_users,
        "total_transactions": total_transactions,
        "flagged_transactions": flagged_transactions,
        "pending_access_requests": pending_requests,
        "today_transactions": today_transactions
    }), 200


@admin_bp.route("/request-access/<user_id>", methods=["POST"])
@admin_required
def request_access(user_id):
    """Admin requests access to a user account."""
    identity = get_jwt_identity()
    data = request.get_json()

    reason = data.get("reason", "").strip()
    if not reason or len(reason) < 10:
        return jsonify({"error": "Please provide a detailed reason (min 10 characters)"}), 400

    user = mongo.db.users.find_one({"_id": ObjectId(user_id), "role": "user"})
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Check if there's already a pending request from this admin for this user
    existing = mongo.db.access_requests.find_one({
        "admin_id": identity["user_id"],
        "user_id": user_id,
        "status": "pending"
    })

    if existing:
        return jsonify({"error": "You already have a pending request for this user"}), 409

    # Create access request (expires in 24 hours if not responded)
    access_request = {
        "admin_id": identity["user_id"],
        "admin_name": identity["name"],
        "user_id": user_id,
        "reason": reason,
        "status": "pending",
        "permission_token": None,
        "requested_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(hours=24)
    }

    result = mongo.db.access_requests.insert_one(access_request)
    request_id = str(result.inserted_id)

    # Send notification email to user
    email_sent = send_access_request_email(
        user_email=user["email"],
        user_name=user["name"],
        admin_name=identity["name"],
        reason=reason,
        request_id=request_id
    )

    log_action(identity["user_id"], "admin", "request_account_access", target_user_id=user_id, details={
        "reason": reason,
        "request_id": request_id
    })

    return jsonify({
        "message": "Access request sent. User will be notified via email.",
        "request_id": request_id,
        "email_sent": email_sent,
        "expires_at": str(access_request["expires_at"])
    }), 201


@admin_bp.route("/access-status/<request_id>", methods=["GET"])
@admin_required
def check_access_status(request_id):
    """Admin checks status of their access request."""
    identity = get_jwt_identity()
    req = mongo.db.access_requests.find_one({
        "_id": ObjectId(request_id),
        "admin_id": identity["user_id"]
    })

    if not req:
        return jsonify({"error": "Access request not found"}), 404

    return jsonify({
        "request_id": request_id,
        "status": req["status"],
        "requested_at": str(req["requested_at"]),
        "expires_at": str(req["expires_at"]),
        "granted_at": str(req.get("granted_at", "")) if req.get("granted_at") else None,
        "permission_token": req.get("permission_token") if req["status"] == "granted" else None
    }), 200


@admin_bp.route("/user-account/<user_id>", methods=["GET"])
@admin_required
def view_user_account(user_id):
    """Admin views user account - requires valid permission token."""
    identity = get_jwt_identity()
    permission_token = request.headers.get("X-Permission-Token")

    if not permission_token:
        return jsonify({"error": "Permission token required in X-Permission-Token header"}), 401

    # Verify the permission token
    payload = verify_permission_token(permission_token)
    if not payload:
        return jsonify({"error": "Invalid or expired permission token"}), 401

    # Ensure token is for this specific admin and user
    if payload["admin_id"] != identity["user_id"] or payload["user_id"] != user_id:
        return jsonify({"error": "Permission token does not match this request"}), 403

    # Verify the access request is still granted in DB
    req = mongo.db.access_requests.find_one({
        "_id": ObjectId(payload["request_id"]),
        "status": "granted"
    })

    if not req:
        return jsonify({"error": "Access has been revoked or request not found"}), 403

    user = mongo.db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Get recent transactions
    transactions = list(mongo.db.transactions.find(
        {"user_id": user_id},
        sort=[("timestamp", -1)],
        limit=20
    ))

    log_action(identity["user_id"], "admin", "viewed_user_account", target_user_id=user_id, details={
        "request_id": payload["request_id"]
    })

    return jsonify({
        "user": {
            "name": user["name"],
            "email": user["email"],
            "phone": user["phone"],
            "account_number": user["account_number"],
            "balance": user["balance"],
            "is_active": user["is_active"],
            "created_at": str(user["created_at"])
        },
        "transactions": [{
            "type": t["type"],
            "amount": t["amount"],
            "description": t.get("description", ""),
            "balance_after": t["balance_after"],
            "is_flagged": t.get("is_flagged", False),
            "timestamp": str(t["timestamp"])
        } for t in transactions],
        "access_note": "This access is logged and monitored."
    }), 200


@admin_bp.route("/users", methods=["GET"])
@admin_required
def list_users():
    """Get list of all users (basic info only)."""
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 10))
    skip = (page - 1) * limit

    users = list(mongo.db.users.find(
        {"role": "user"},
        {"password": 0},
        skip=skip,
        limit=limit
    ))

    total = mongo.db.users.count_documents({"role": "user"})

    return jsonify({
        "users": [{
            "user_id": str(u["_id"]),
            "name": u["name"],
            "email": u["email"],
            "account_number": u["account_number"],
            "balance": u["balance"],
            "is_active": u["is_active"]
        } for u in users],
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit
    }), 200


@admin_bp.route("/flagged-transactions", methods=["GET"])
@admin_required
def get_flagged_transactions():
    """Get all fraud-flagged transactions."""
    transactions = list(mongo.db.transactions.find(
        {"is_flagged": True},
        sort=[("timestamp", -1)],
        limit=50
    ))

    result = []
    for t in transactions:
        user = mongo.db.users.find_one({"_id": ObjectId(t["user_id"])}) if t.get("user_id") else None
        result.append({
            "transaction_id": str(t["_id"]),
            "user_name": user["name"] if user else "Unknown",
            "account_number": user["account_number"] if user else "Unknown",
            "type": t["type"],
            "amount": t["amount"],
            "fraud_score": t.get("fraud_score", 0),
            "timestamp": str(t["timestamp"])
        })

    return jsonify({"flagged_transactions": result}), 200


@admin_bp.route("/audit-logs", methods=["GET"])
@admin_required
def get_audit_logs():
    """Get system audit logs."""
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 20))
    skip = (page - 1) * limit

    logs = list(mongo.db.audit_logs.find(
        {},
        sort=[("timestamp", -1)],
        skip=skip,
        limit=limit
    ))

    total = mongo.db.audit_logs.count_documents({})

    return jsonify({
        "logs": [{
            "log_id": str(log["_id"]),
            "actor_id": log["actor_id"],
            "actor_role": log["actor_role"],
            "action": log["action"],
            "target_user_id": log.get("target_user_id"),
            "details": log.get("details", {}),
            "ip_address": log.get("ip_address"),
            "timestamp": str(log["timestamp"])
        } for log in logs],
        "total": total,
        "page": page
    }), 200


@admin_bp.route("/toggle-account/<user_id>", methods=["POST"])
@admin_required
def toggle_account(user_id):
    """Activate or deactivate a user account."""
    identity = get_jwt_identity()
    user = mongo.db.users.find_one({"_id": ObjectId(user_id), "role": "user"})

    if not user:
        return jsonify({"error": "User not found"}), 404

    new_status = not user["is_active"]
    mongo.db.users.update_one({"_id": user["_id"]}, {"$set": {"is_active": new_status}})

    action = "activated_account" if new_status else "deactivated_account"
    log_action(identity["user_id"], "admin", action, target_user_id=user_id)

    return jsonify({
        "message": f"Account {'activated' if new_status else 'deactivated'} successfully",
        "is_active": new_status
    }), 200


@admin_bp.route("/my-requests", methods=["GET"])
@admin_required
def my_requests():
    """Get all access requests sent by this admin."""
    identity = get_jwt_identity()

    requests_list = list(mongo.db.access_requests.find(
        {"admin_id": identity["user_id"]},
        sort=[("requested_at", -1)],
        limit=20
    ))

    result = []
    for r in requests_list:
        user = mongo.db.users.find_one({"_id": ObjectId(r["user_id"])})
        result.append({
            "request_id": str(r["_id"]),
            "user_id": r["user_id"],
            "user_name": user["name"] if user else "Unknown",
            "user_email": user["email"] if user else "",
            "account_number": user["account_number"] if user else "",
            "reason": r["reason"],
            "status": r["status"],
            "permission_token": r.get("permission_token") if r["status"] == "granted" else None,
            "requested_at": str(r["requested_at"]),
            "expires_at": str(r["expires_at"]),
            "granted_at": str(r["granted_at"]) if r.get("granted_at") else None
        })

    return jsonify({"requests": result}), 200
