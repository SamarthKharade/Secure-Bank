from flask_mail import Message
from app import mail
from flask import current_app


def send_access_request_email(user_email, user_name, admin_name, reason, request_id):
    """Send email to user when admin requests access to their account."""
    approve_link = f"http://localhost:5000/api/v1/user/grant-access/{request_id}"
    deny_link = f"http://localhost:5000/api/v1/user/deny-access/{request_id}"

    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 20px;">
        <div style="background: #003366; padding: 20px; border-radius: 8px 8px 0 0;">
            <h2 style="color: white; margin: 0;">SecureBank — Account Access Request</h2>
        </div>
        <div style="background: #f9f9f9; padding: 30px; border: 1px solid #ddd; border-radius: 0 0 8px 8px;">
            <p>Dear <strong>{user_name}</strong>,</p>
            <p>Bank administrator <strong>{admin_name}</strong> has requested access to your account.</p>
            <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0;">
                <strong>Reason:</strong> {reason}
            </div>
            <p>This access will expire in <strong>30 minutes</strong> if granted.</p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{approve_link}" style="background: #28a745; color: white; padding: 12px 30px; 
                   text-decoration: none; border-radius: 5px; margin-right: 10px; font-weight: bold;">
                   ✅ Grant Access
                </a>
                <a href="{deny_link}" style="background: #dc3545; color: white; padding: 12px 30px; 
                   text-decoration: none; border-radius: 5px; font-weight: bold;">
                   ❌ Deny Access
                </a>
            </div>
            <p style="color: #666; font-size: 12px;">
                If you did not expect this request, please deny it and contact support immediately.
            </p>
        </div>
    </body>
    </html>
    """

    msg = Message(
        subject="[SecureBank] Admin Access Request — Action Required",
        recipients=[user_email],
        html=html_body
    )

    try:
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Email send failed: {e}")
        return False


def send_access_decision_email(admin_email, admin_name, user_name, decision):
    """Notify admin about user's decision on access request."""
    color = "#28a745" if decision == "granted" else "#dc3545"
    icon = "✅" if decision == "granted" else "❌"

    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 20px;">
        <div style="background: #003366; padding: 20px; border-radius: 8px 8px 0 0;">
            <h2 style="color: white; margin: 0;">SecureBank — Access Request Update</h2>
        </div>
        <div style="background: #f9f9f9; padding: 30px; border: 1px solid #ddd; border-radius: 0 0 8px 8px;">
            <p>Dear <strong>{admin_name}</strong>,</p>
            <div style="background: {color}22; border-left: 4px solid {color}; padding: 15px; margin: 20px 0;">
                <h3 style="color: {color}; margin: 0;">{icon} Access {decision.capitalize()}</h3>
                <p style="margin: 5px 0;">User <strong>{user_name}</strong> has <strong>{decision}</strong> your access request.</p>
            </div>
            {"<p>You now have <strong>30 minutes</strong> to access the account.</p>" if decision == "granted" else ""}
        </div>
    </body>
    </html>
    """

    msg = Message(
        subject=f"[SecureBank] Access {decision.capitalize()} by {user_name}",
        recipients=[admin_email],
        html=html_body
    )

    try:
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Email send failed: {e}")
        return False


def send_transaction_alert_email(user_email, user_name, txn_type, amount, balance):
    """Send transaction alert to user."""
    color = "#dc3545" if txn_type == "debit" else "#28a745"
    icon = "📤" if txn_type == "debit" else "📥"

    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 20px;">
        <div style="background: #003366; padding: 20px; border-radius: 8px 8px 0 0;">
            <h2 style="color: white; margin: 0;">SecureBank — Transaction Alert</h2>
        </div>
        <div style="background: #f9f9f9; padding: 30px; border: 1px solid #ddd; border-radius: 0 0 8px 8px;">
            <p>Dear <strong>{user_name}</strong>,</p>
            <div style="background: {color}11; border-left: 4px solid {color}; padding: 15px; margin: 20px 0;">
                <p style="margin: 0;">{icon} <strong>{txn_type.upper()}</strong> of 
                <strong style="color:{color};">₹{amount:,.2f}</strong> was processed.</p>
                <p style="margin: 5px 0;">Available Balance: <strong>₹{balance:,.2f}</strong></p>
            </div>
        </div>
    </body>
    </html>
    """

    msg = Message(
        subject=f"[SecureBank] {txn_type.capitalize()} Alert — ₹{amount}",
        recipients=[user_email],
        html=html_body
    )

    try:
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Email send failed: {e}")
        return False
