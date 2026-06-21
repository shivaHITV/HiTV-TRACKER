"""
models.py — SQLAlchemy database models for HiTV Production Manager.
Defines User, Client, and Task with relationships and helper methods.
"""

from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


db = SQLAlchemy()

# ──────────────────────────────────────────────
# Constants — role and status choices
# ──────────────────────────────────────────────

ROLES = [
    ("admin", "Admin"),
    ("videographer", "Videographer"),
    ("editor", "Editor"),
    ("marketer", "Marketer"),
]

STATUSES = [
    ("pending", "Pending"),
    ("ongoing", "Ongoing"),
    ("completed", "Completed"),
]


# ──────────────────────────────────────────────
# User model
# ──────────────────────────────────────────────

class User(UserMixin, db.Model):
    """Represents an authenticated user of the system."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    # Role determines which tasks the user can see (admin sees all)
    role = db.Column(db.String(20), nullable=False, default="videographer")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Back-reference: tasks assigned to this user
    assigned_tasks = db.relationship(
        "Task", foreign_keys="Task.assigned_to_id", back_populates="assignee", lazy="dynamic"
    )
    # Back-reference: tasks created by this admin
    created_tasks = db.relationship(
        "Task", foreign_keys="Task.created_by_id", back_populates="creator", lazy="dynamic"
    )

    def set_password(self, password: str) -> None:
        """Hash and store a plaintext password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Return True if the given password matches the stored hash."""
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        """Convenience property — True when the user's role is admin."""
        return self.role == "admin"

    def __repr__(self) -> str:
        return f"<User {self.username} ({self.role})>"


# ──────────────────────────────────────────────
# Client model
# ──────────────────────────────────────────────

class Client(db.Model):
    """Represents a production client that tasks are tied to."""

    __tablename__ = "clients"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    contact_email = db.Column(db.String(120))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Back-reference to all tasks for this client
    tasks = db.relationship("Task", back_populates="client", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Client {self.name}>"


# ──────────────────────────────────────────────
# Task model
# ──────────────────────────────────────────────

class Task(db.Model):
    """Represents a production task tied to a client and assigned to a user."""

    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)

    # Foreign key to Client
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False)
    client = db.relationship("Client", back_populates="tasks")

    # The required role for this task (videographer / editor / marketer)
    role = db.Column(db.String(20), nullable=False)

    # User assigned to complete this task
    assigned_to_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    assignee = db.relationship("User", foreign_keys=[assigned_to_id], back_populates="assigned_tasks")

    # Admin who created the task
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    creator = db.relationship("User", foreign_keys=[created_by_id], back_populates="created_tasks")

    # Workflow status
    status = db.Column(db.String(20), nullable=False, default="pending")

    # Deadline stored as a date
    deadline = db.Column(db.Date, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def is_overdue(self) -> bool:
        """Return True if the deadline has passed and task is not completed."""
        if self.deadline and self.status != "completed":
            return self.deadline < date.today()
        return False

    @property
    def status_badge_class(self) -> str:
        """Return a CSS class name for the status badge."""
        return {
            "pending": "badge-pending",
            "ongoing": "badge-ongoing",
            "completed": "badge-completed",
        }.get(self.status, "badge-pending")

    def __repr__(self) -> str:
        return f"<Task {self.title} [{self.status}]>"


# ──────────────────────────────────────────────
# Notification model
# ──────────────────────────────────────────────

# Notification type choices
NOTIF_TYPES = {
    "assigned":   "Task Assigned",
    "unassigned": "Task Unassigned",
    "deadline":   "Deadline Reminder",
    "status":     "Status Changed",
}


class Notification(db.Model):
    """
    Stores in-app notifications for a user.
    Created automatically on task assignment and deadline proximity.
    """

    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)

    # Recipient
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    user = db.relationship("User", backref=db.backref("notifications", lazy="dynamic"))

    # Type: "assigned" | "unassigned" | "deadline" | "status"
    notif_type = db.Column(db.String(20), nullable=False, default="assigned")

    # The task this notification relates to (nullable — task may be deleted)
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    task = db.relationship("Task", backref=db.backref("notifications", lazy="dynamic",
                                                        passive_deletes=True))

    # Human-readable message shown in the UI
    message = db.Column(db.String(500), nullable=False)

    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def type_icon(self) -> str:
        """Emoji icon for the notification type."""
        return {
            "assigned":   "📋",
            "unassigned": "🔕",
            "deadline":   "⏰",
            "status":     "🔄",
        }.get(self.notif_type, "🔔")

    @property
    def type_label(self) -> str:
        return NOTIF_TYPES.get(self.notif_type, "Notification")

    def __repr__(self) -> str:
        return f"<Notification {self.notif_type} → user {self.user_id}>"


# ──────────────────────────────────────────────
# Activity Log model
# ──────────────────────────────────────────────

# Event types logged to the activity timeline
ACTIVITY_EVENTS = {
    "created":          "Task Created",
    "status_changed":   "Status Changed",
    "reassigned":       "Reassigned",
    "unassigned":       "Unassigned",
    "deadline_changed": "Deadline Changed",
    "title_changed":    "Title Changed",
    "description_changed": "Description Updated",
    "role_changed":     "Required Role Changed",
}


class ActivityLog(db.Model):
    """
    Immutable audit trail of significant task events.
    Written on create, status update, reassignment, and field edits.
    """

    __tablename__ = "activity_log"

    id = db.Column(db.Integer, primary_key=True)

    # The task this event belongs to (kept even if task deleted, set null)
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True)
    task = db.relationship("Task", backref=db.backref("activity_log", lazy="dynamic",
                                                       order_by="ActivityLog.created_at",
                                                       passive_deletes=True))

    # Who triggered the event
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    actor = db.relationship("User", backref=db.backref("activity_log", lazy="dynamic"))

    # Short event type key
    event = db.Column(db.String(30), nullable=False)

    # Human-readable summary, e.g. "Status changed from Pending → Ongoing"
    detail = db.Column(db.String(500), nullable=False, default="")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def event_label(self) -> str:
        return ACTIVITY_EVENTS.get(self.event, self.event)

    @property
    def event_icon(self) -> str:
        return {
            "created":             "✨",
            "status_changed":      "🔄",
            "reassigned":          "👤",
            "unassigned":          "🚫",
            "deadline_changed":    "📅",
            "title_changed":       "✏️",
            "description_changed": "📝",
            "role_changed":        "🎭",
        }.get(self.event, "📌")

    def __repr__(self) -> str:
        return f"<ActivityLog {self.event} task={self.task_id} actor={self.actor_id}>"


# ──────────────────────────────────────────────
# Comment model
# ──────────────────────────────────────────────

class Comment(db.Model):
    """
    A comment left by any team member or admin on a task.
    Supports a simple linear thread — newest comments at the bottom.
    """

    __tablename__ = "comments"

    id = db.Column(db.Integer, primary_key=True)

    # The task this comment belongs to
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    task = db.relationship("Task", backref=db.backref("comments", lazy="dynamic",
                                                       order_by="Comment.created_at",
                                                       passive_deletes=True))

    # Author
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    author = db.relationship("User", backref=db.backref("comments", lazy="dynamic"))

    # Comment body (plain text)
    body = db.Column(db.Text, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def is_edited(self) -> bool:
        """True if the comment was updated after creation (with a 5-second grace window)."""
        if self.updated_at and self.created_at:
            return (self.updated_at - self.created_at).total_seconds() > 5
        return False

    def __repr__(self) -> str:
        return f"<Comment by user {self.author_id} on task {self.task_id}>"
