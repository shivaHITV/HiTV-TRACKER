"""
config.py — Application configuration settings.
Loads environment variables and defines base, development, and production configs.
"""

import os
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Base configuration shared by all environments."""

    # Secret key for session signing and CSRF protection
    SECRET_KEY = os.environ.get("SESSION_SECRET", "hitv-dev-secret-change-in-prod")

    # SQLite database stored in the project directory
    # Use HITV_DATABASE_URL to avoid inheriting the Node.js workspace PostgreSQL URL
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "HITV_DATABASE_URL",
        f"sqlite:///{os.path.join(BASE_DIR, 'hitv.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # WTForms CSRF protection
    WTF_CSRF_ENABLED = True

    # Upload folder for any future file attachments
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

    # ── Flask-Mail (optional — leave MAIL_SERVER blank to disable email) ──
    # Configure these via environment variables or a .env file.
    # Example: Gmail with App Password:
    #   MAIL_SERVER=smtp.gmail.com  MAIL_PORT=587  MAIL_USE_TLS=True
    #   MAIL_USERNAME=you@gmail.com  MAIL_PASSWORD=<app-password>
    MAIL_SERVER   = os.environ.get("MAIL_SERVER", "")
    MAIL_PORT     = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS  = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USE_SSL  = os.environ.get("MAIL_USE_SSL", "false").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get(
        "MAIL_DEFAULT_SENDER",
        os.environ.get("MAIL_USERNAME", "noreply@hitv.com"),
    )

    # How many days before a deadline to send a reminder
    DEADLINE_REMINDER_DAYS = int(os.environ.get("DEADLINE_REMINDER_DAYS", 2))


class DevelopmentConfig(Config):
    """Development-specific config with debug enabled."""
    DEBUG = True


class ProductionConfig(Config):
    """Production config — debug off."""
    DEBUG = False


# Map string names to config objects
config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
