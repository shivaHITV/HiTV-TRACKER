"""
activity.py — Helper functions for writing to the ActivityLog.
Import and call these wherever task state changes occur.
"""

from models import db, ActivityLog, User


def _username(user_id):
    """Return username string for a user_id, or 'Unknown'."""
    if not user_id:
        return "Unknown"
    u = db.session.get(User, user_id)
    return u.username if u else "Unknown"


def log_task_created(task, actor_id: int) -> None:
    """Log the initial creation of a task."""
    assignee = _username(task.assigned_to_id) if task.assigned_to_id else "Unassigned"
    entry = ActivityLog(
        task_id=task.id,
        actor_id=actor_id,
        event="created",
        detail=f'Task created and assigned to {assignee}.',
    )
    db.session.add(entry)
    db.session.commit()


def log_status_change(task, old_status: str, new_status: str, actor_id: int) -> None:
    """Log a status transition."""
    if old_status == new_status:
        return
    entry = ActivityLog(
        task_id=task.id,
        actor_id=actor_id,
        event="status_changed",
        detail=f'Status changed from {old_status.capitalize()} → {new_status.capitalize()}.',
    )
    db.session.add(entry)
    db.session.commit()


def log_reassignment(task, old_assignee_id, new_assignee_id, actor_id: int) -> None:
    """Log an assignee change (including unassignment)."""
    old_name = _username(old_assignee_id) if old_assignee_id else "Unassigned"
    new_name = _username(new_assignee_id) if new_assignee_id else "Unassigned"

    if old_assignee_id == new_assignee_id:
        return

    event = "unassigned" if not new_assignee_id else "reassigned"
    entry = ActivityLog(
        task_id=task.id,
        actor_id=actor_id,
        event=event,
        detail=f'Assignee changed from {old_name} → {new_name}.',
    )
    db.session.add(entry)
    db.session.commit()


def log_field_changes(task, changes: dict, actor_id: int) -> None:
    """
    Log one entry per changed field.
    `changes` is a dict of field_name → (old_value, new_value).
    Supported keys: title, description, deadline, role.
    """
    field_map = {
        "title":       ("title_changed",       lambda o, n: f'Title changed from "{o}" → "{n}".'),
        "description": ("description_changed", lambda o, n: "Description updated."),
        "deadline":    ("deadline_changed",     lambda o, n: f'Deadline changed from {o or "none"} → {n or "none"}.'),
        "role":        ("role_changed",         lambda o, n: f'Required role changed from {o.capitalize()} → {n.capitalize()}.'),
    }
    for field, (old_val, new_val) in changes.items():
        if field not in field_map or old_val == new_val:
            continue
        event_key, fmt = field_map[field]
        entry = ActivityLog(
            task_id=task.id,
            actor_id=actor_id,
            event=event_key,
            detail=fmt(old_val, new_val),
        )
        db.session.add(entry)
    db.session.commit()
