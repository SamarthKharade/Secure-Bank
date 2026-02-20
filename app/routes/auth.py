from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from app import mongo, limiter
import bcrypt
import random
import string
from datetime import datetime

auth_bp = Blueprint("auth", __name__)


def generate_account_number():
    return "ACC" + "".join(random.choices(string.digits, k=10))


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def check_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


@auth_bp.route("/register", methods=["POST"])
@limiter.limit("10 per hour")
def register():
    data = request.get_json()
    required = ["name", "email", "phone", "password"]

    if not all(k in data for k in required):
        return jsonify({"error": "Missing required fields"}), 400

    # Check duplicate
    if mongo.db.users.find_one({"email": data["email"]}):
        return jsonify({"error": "Email already registered"}), 409

    user = {
        "name": data["name"],
        "email": data["email"].lower(),
        "phone": data["phone"],
        "password": hash_password(data["password"]),
        "account_number": generate_account_number(),
        "balance": 0.0,
        "role": "user",
        "is_active": True,
        "notification_preference": data.get("notification_preference", "email"),
        "failed_login_attempts": 0,
        "is_locked": False,
        "created_at": datetime.utcnow()
    }

    result = mongo.db.users.insert_one(user)
    return jsonify({
        "message": "Account created successfully",
        "account_number": user["account_number"],
        "user_id": str(result.inserted_id)
    }), 201


@auth_bp.route("/login", methods=["POST"])
@limiter.limit("20 per hour")
def login():
    data = request.get_json()

    if not data.get("email") or not data.get("password"):
        return jsonify({"error": "Email and password required"}), 400

    user = mongo.db.users.find_one({"email": data["email"].lower()})

    if not user:
        return jsonify({"error": "Invalid credentials"}), 401

    if user.get("is_locked"):
        return jsonify({"error": "Account locked due to multiple failed attempts. Contact support."}), 403

    if not check_password(data["password"], user["password"]):
        # Increment failed attempts
        attempts = user.get("failed_login_attempts", 0) + 1
        update = {"failed_login_attempts": attempts}
        if attempts >= 5:
            update["is_locked"] = True
        mongo.db.users.update_one({"_id": user["_id"]}, {"$set": update})
        remaining = max(0, 5 - attempts)
        return jsonify({"error": f"Invalid credentials. {remaining} attempts remaining."}), 401

    if not user.get("is_active"):
        return jsonify({"error": "Account is deactivated"}), 403

    # Reset failed attempts
    mongo.db.users.update_one({"_id": user["_id"]}, {"$set": {"failed_login_attempts": 0}})

    token = create_access_token(identity={
        "user_id": str(user["_id"]),
        "email": user["email"],
        "role": user["role"],
        "name": user["name"]
    })

    return jsonify({
        "message": "Login successful",
        "token": token,
        "role": user["role"],
        "name": user["name"]
    }), 200


@auth_bp.route("/register-admin", methods=["POST"])
@limiter.limit("5 per hour")
def register_admin():
    """Register a bank admin. In production this should be protected."""
    data = request.get_json()
    required = ["name", "email", "phone", "password", "admin_secret"]

    if not all(k in data for k in required):
        return jsonify({"error": "Missing required fields"}), 400

    # Simple admin secret check (in production use env variable)
    if data["admin_secret"] != "BANK_ADMIN_SECRET_2024":
        return jsonify({"error": "Invalid admin secret"}), 403

    if mongo.db.users.find_one({"email": data["email"]}):
        return jsonify({"error": "Email already registered"}), 409

    admin = {
        "name": data["name"],
        "email": data["email"].lower(),
        "phone": data["phone"],
        "password": hash_password(data["password"]),
        "account_number": None,
        "balance": None,
        "role": "admin",
        "is_active": True,
        "failed_login_attempts": 0,
        "is_locked": False,
        "created_at": datetime.utcnow()
    }

    result = mongo.db.users.insert_one(admin)
    return jsonify({
        "message": "Admin account created successfully",
        "admin_id": str(result.inserted_id)
    }), 201
