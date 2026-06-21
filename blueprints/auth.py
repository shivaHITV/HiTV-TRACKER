"""
blueprints/auth.py — Authentication routes (login / logout).
Uses Flask-Login to manage user sessions securely.
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User
from forms import LoginForm

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Show login form and authenticate the user."""
    # Already logged-in users go straight to dashboard
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data.strip()).first()

        if user and user.check_password(form.password.data):
            login_user(user)
            flash(f"Welcome back, {user.username}!", "success")
            # Redirect to the page they were trying to access, or dashboard
            next_page = request.args.get("next")
            return redirect(next_page or url_for("main.dashboard"))

        flash("Invalid username or password.", "danger")

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    """Log the current user out and redirect to login."""
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
