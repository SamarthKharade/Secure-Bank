from datetime import datetime
from app import mongo
from flask import request as flask_request


def log_action(actor_id: str, actor_role: str, action: str, target_user_id: str = None, details: dict = None):
    """Log any significant action in the system."""
    log_entry = {
        "actor_id": actor_id,
        "actor_role": actor_role,  # "user" or "admin"
        "action": action,
        "target_user_id": target_user_id,
        "details": details or {},
        "ip_address": flask_request.remote_addr,
        "user_agent": flask_request.headers.get("User-Agent", "unknown"),
        "timestamp": datetime.utcnow()
    }
    mongo.db.audit_logs.insert_one(log_entry)
