"""
blueprints/notifications.py — In-app notification routes.
Lists, marks read, and clears notifications for the current user.
"""

from flask import Blueprint, render_template, redirect, url_for, request, jsonify
from flask_login import login_required, current_user
from models import db, Notification

notifications_bp = Blueprint("notifications", __name__, url_prefix="/notifications")


@notifications_bp.route("/")
@login_required
def list_notifications():
    """Show all notifications for the current user, newest first."""
    notifs = (
        Notification.query
        .filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(100)
        .all()
    )
    # Mark all as read when the page is opened
    unread = [n for n in notifs if not n.is_read]
    for n in unread:
        n.is_read = True
    if unread:
        db.session.commit()

    return render_template("notifications/list.html", notifications=notifs)


@notifications_bp.route("/mark-read/<int:notif_id>", methods=["POST"])
@login_required
def mark_read(notif_id):
    """Mark a single notification as read."""
    notif = Notification.query.filter_by(id=notif_id, user_id=current_user.id).first_or_404()
    notif.is_read = True
    db.session.commit()
    return redirect(request.referrer or url_for("notifications.list_notifications"))


@notifications_bp.route("/mark-all-read", methods=["POST"])
@login_required
def mark_all_read():
    """Mark all of the current user's notifications as read."""
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return redirect(url_for("notifications.list_notifications"))


@notifications_bp.route("/clear", methods=["POST"])
@login_required
def clear_all():
    """Delete all read notifications for the current user."""
    Notification.query.filter_by(user_id=current_user.id, is_read=True).delete()
    db.session.commit()
    return redirect(url_for("notifications.list_notifications"))


@notifications_bp.route("/unread-count")
@login_required
def unread_count():
    """JSON endpoint returning the unread count (used by topbar badge)."""
    count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({"count": count})
