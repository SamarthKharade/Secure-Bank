import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/bankapp")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "fallback-secret")
    PERMISSION_SECRET = os.getenv("PERMISSION_SECRET", "fallback-permission-secret")
    JWT_ACCESS_TOKEN_EXPIRES = 3600  # 1 hour

    # Mail config
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "True") == "True"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER")

    # Rate limiting
    RATELIMIT_DEFAULT = "100 per hour"
