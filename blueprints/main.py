"""
blueprints/main.py — Main routes: dashboard and home redirect.
Also triggers deadline notifications on dashboard load (once per day per user).
"""

from datetime import date, timedelta
from flask import Blueprint, render_template, redirect, url_for, session
from flask_login import login_required, current_user
from sqlalchemy import func
from models import db, Task, Client, User, STATUSES

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    """Root redirect — send authenticated users to dashboard, others to login."""
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("auth.login"))


@main_bp.route("/dashboard")
@login_required
def dashboard():
    """
    Main dashboard.
    - Admins see aggregate stats across all tasks, clients, and users.
    - Regular users see only tasks assigned to them.
    Also runs deadline notifications once per calendar day per user.
    """
    _maybe_check_deadlines()

    if current_user.is_admin:
        # ── Admin stats ──────────────────────────────────────────────
        total_tasks = Task.query.count()
        total_clients = Client.query.count()
        total_users = User.query.filter(User.role != "admin").count()

        status_counts = {
            status: Task.query.filter_by(status=status).count()
            for status, _ in STATUSES
        }

        client_stats = (
            db.session.query(Client.name, func.count(Task.id))
            .join(Task, Client.id == Task.client_id)
            .group_by(Client.id)
            .all()
        )

        recent_tasks = Task.query.order_by(Task.created_at.desc()).limit(10).all()
        overdue_tasks = [t for t in Task.query.filter(Task.status != "completed").all()
                         if t.is_overdue]

        return render_template(
            "dashboard.html",
            total_tasks=total_tasks,
            total_clients=total_clients,
            total_users=total_users,
            status_counts=status_counts,
            client_stats=client_stats,
            recent_tasks=recent_tasks,
            overdue_count=len(overdue_tasks),
        )

    else:
        # ── Regular user stats ───────────────────────────────────────
        my_tasks = Task.query.filter_by(assigned_to_id=current_user.id)

        status_counts = {
            status: my_tasks.filter_by(status=status).count()
            for status, _ in STATUSES
        }

        recent_tasks = my_tasks.order_by(Task.updated_at.desc()).limit(10).all()
        overdue_tasks = [t for t in my_tasks.filter(Task.status != "completed").all()
                         if t.is_overdue]

        return render_template(
            "dashboard.html",
            status_counts=status_counts,
            recent_tasks=recent_tasks,
            overdue_count=len(overdue_tasks),
            total_tasks=my_tasks.count(),
        )


def _maybe_check_deadlines():
    """
    Run deadline notification checks at most once per calendar day per user.
    Stores a 'last_deadline_check' date in the Flask session to avoid
    hammering the DB on every page load.
    """
    today_str = date.today().isoformat()
    session_key = f"deadline_checked_{current_user.id}"

    if session.get(session_key) == today_str:
        return  # Already checked today

    try:
        from notify import check_and_create_deadline_notifications
        from flask import current_app
        days = current_app.config.get("DEADLINE_REMINDER_DAYS", 2)
        check_and_create_deadline_notifications(days_ahead=days)
    except Exception:
        pass  # Never break dashboard over notification errors

    session[session_key] = today_str
