"""
extensions.py — Flask extension instances shared across the application.
Import from here to avoid circular imports.
"""

from flask_login import LoginManager
from flask_mail import Mail
from models import db

# LoginManager handles user session management
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "warning"

# Mail handles outgoing SMTP email (optional — skipped if not configured)
mail = Mail()
