import jwt
import datetime
from flask import current_app


def generate_permission_token(admin_id: str, user_id: str, request_id: str) -> str:
    """Generate a short-lived JWT permission token for admin access."""
    payload = {
        "admin_id": admin_id,
        "user_id": user_id,
        "request_id": request_id,
        "type": "admin_permission",
        "iat": datetime.datetime.utcnow(),
        "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=30)
    }
    return jwt.encode(payload, current_app.config["PERMISSION_SECRET"], algorithm="HS256")


def verify_permission_token(token: str) -> dict | None:
    """Verify and decode a permission token. Returns payload or None."""
    try:
        payload = jwt.decode(token, current_app.config["PERMISSION_SECRET"], algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
