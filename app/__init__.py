from flask import Flask, send_from_directory, redirect
from flask_pymongo import PyMongo
from flask_jwt_extended import JWTManager
from flask_mail import Mail
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
from .config import Config

mongo = PyMongo()
jwt = JWTManager()
mail = Mail()
limiter = Limiter(key_func=get_remote_address)


def create_app():
    # Point Flask to the frontend folder for static files
    frontend_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

    app = Flask(__name__, static_folder=frontend_folder, static_url_path="")
    app.config.from_object(Config)

    # Init extensions
    mongo.init_app(app)
    jwt.init_app(app)
    mail.init_app(app)
    CORS(app)
    limiter.init_app(app)

    # ── Serve frontend pages ──────────────────────────────
    @app.route("/")
    def index():
        return send_from_directory(frontend_folder, "login.html")

    @app.route("/login")
    def login_page():
        return send_from_directory(frontend_folder, "login.html")

    @app.route("/dashboard")
    def dashboard_page():
        return send_from_directory(frontend_folder, "dashboard.html")

    @app.route("/transactions")
    def transactions_page():
        return send_from_directory(frontend_folder, "transactions.html")

    @app.route("/admin")
    def admin_page():
        return send_from_directory(frontend_folder, "admin.html")

    # ── Register API blueprints ───────────────────────────
    from .routes.auth import auth_bp
    from .routes.user import user_bp
    from .routes.admin import admin_bp
    from .routes.ml import ml_bp

    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(user_bp, url_prefix="/api/v1/user")
    app.register_blueprint(admin_bp, url_prefix="/api/v1/admin")
    app.register_blueprint(ml_bp, url_prefix="/api/v1/ml")

    return app
