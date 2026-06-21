"""
notify.py — Shared helpers for creating in-app notifications and sending email alerts.

Usage:
    from notify import notify_task_assigned, notify_deadline_approaching
"""

import logging
from datetime import date, timedelta
from flask import current_app, url_for
from models import db, Notification, Task, User

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# In-app notification helpers
# ──────────────────────────────────────────────────────────────

def _create_notification(user_id: int, notif_type: str, task_id: int, message: str) -> Notification:
    """
    Persist a Notification record.
    Deduplicates: if an unread notification of the same type+task already
    exists, update its message rather than inserting a duplicate.
    """
    existing = Notification.query.filter_by(
        user_id=user_id, notif_type=notif_type, task_id=task_id, is_read=False
    ).first()

    if existing:
        existing.message = message
        db.session.commit()
        return existing

    notif = Notification(
        user_id=user_id,
        notif_type=notif_type,
        task_id=task_id,
        message=message,
    )
    db.session.add(notif)
    db.session.commit()
    return notif


# ──────────────────────────────────────────────────────────────
# Task-assignment notification
# ──────────────────────────────────────────────────────────────

def notify_task_assigned(task) -> None:
    """
    Create an in-app notification (and optional email) when a task is assigned.
    Safe to call even if task.assignee is None — does nothing in that case.
    """
    if not task.assigned_to_id:
        return

    deadline_str = ""
    if task.deadline:
        deadline_str = f" — due {task.deadline.strftime('%b %d, %Y')}"

    message = (
        f"You've been assigned a new task: \"{task.title}\" "
        f"for {task.client.name}{deadline_str}."
    )

    _create_notification(task.assigned_to_id, "assigned", task.id, message)

    # Optional email
    _send_email(
        to=task.assignee.email,
        subject=f"[HiTV] New task assigned: {task.title}",
        body=(
            f"Hi {task.assignee.username},\n\n"
            f"You have been assigned a new production task:\n\n"
            f"  Task:    {task.title}\n"
            f"  Client:  {task.client.name}\n"
            f"  Role:    {task.role.capitalize()}\n"
            f"  Status:  {task.status.capitalize()}\n"
            f"  Deadline:{' ' + task.deadline.strftime('%B %d, %Y') if task.deadline else ' None'}\n\n"
            f"Log in to HiTV Production Manager to view and update this task.\n\n"
            f"— HiTV Admin"
        ),
    )


# ──────────────────────────────────────────────────────────────
# Task re-assignment notification (assignee changed)
# ──────────────────────────────────────────────────────────────

def notify_task_reassigned(task, old_assignee_id: int) -> None:
    """Notify the new assignee when a task is reassigned."""
    notify_task_assigned(task)

    if old_assignee_id and old_assignee_id != task.assigned_to_id:
        old_user = User.query.get(old_assignee_id)
        if old_user:
            message = f"You've been unassigned from \"{task.title}\" for {task.client.name}."
            _create_notification(old_assignee_id, "unassigned", task.id, message)


# ──────────────────────────────────────────────────────────────
# Deadline-approaching notifications
# ──────────────────────────────────────────────────────────────

def check_and_create_deadline_notifications(days_ahead: int = 2) -> int:
    """
    Scan all non-completed tasks with deadlines within `days_ahead` days.
    Create in-app notifications (and optional emails) for assigned users.
    Returns the number of new notifications created.

    Call this once per day (e.g. on dashboard load, gated by a daily flag).
    """
    threshold = date.today() + timedelta(days=days_ahead)
    today = date.today()

    tasks = (
        Task.query
        .filter(
            Task.status != "completed",
            Task.deadline != None,          # noqa: E711
            Task.deadline >= today,
            Task.deadline <= threshold,
            Task.assigned_to_id != None,    # noqa: E711
        )
        .all()
    )

    created = 0
    for task in tasks:
        days_left = (task.deadline - today).days
        if days_left == 0:
            when = "today"
        elif days_left == 1:
            when = "tomorrow"
        else:
            when = f"in {days_left} days"

        message = (
            f"⏰ Deadline reminder: \"{task.title}\" for {task.client.name} "
            f"is due {when} ({task.deadline.strftime('%b %d, %Y')})."
        )

        notif = _create_notification(task.assigned_to_id, "deadline", task.id, message)
        if notif:
            created += 1

        # Email reminder (once per day — dedup handled by _create_notification)
        _send_email(
            to=task.assignee.email,
            subject=f"[HiTV] Deadline reminder: {task.title} due {when}",
            body=(
                f"Hi {task.assignee.username},\n\n"
                f"This is a reminder that your task is due soon:\n\n"
                f"  Task:     {task.title}\n"
                f"  Client:   {task.client.name}\n"
                f"  Deadline: {task.deadline.strftime('%B %d, %Y')} ({when})\n"
                f"  Status:   {task.status.capitalize()}\n\n"
                f"Log in to HiTV Production Manager to update your progress.\n\n"
                f"— HiTV Admin"
            ),
        )

    return created


# ──────────────────────────────────────────────────────────────
# Email helper — silently skipped if SMTP is not configured
# ──────────────────────────────────────────────────────────────

def _send_email(to: str, subject: str, body: str) -> bool:
    """
    Send a plain-text email via Flask-Mail.
    Returns True on success, False if email is not configured or sending fails.
    Errors are logged as warnings — they never raise to the caller.
    """
    try:
        from flask_mail import Message
        from extensions import mail

        if not current_app.config.get("MAIL_SERVER"):
            return False  # Email not configured — skip silently

        msg = Message(
            subject=subject,
            recipients=[to],
            body=body,
        )
        mail.send(msg)
        return True
    except Exception as exc:
        logger.warning("Email send failed (%s → %s): %s", subject, to, exc)
        return False
