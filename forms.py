"""
forms.py — WTForms form definitions for HiTV Production Manager.
All user-facing forms are defined here with validation rules.
"""

from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, SelectField, TextAreaField,
    DateField, SubmitField, EmailField
)
from wtforms.validators import (
    DataRequired, Email, EqualTo, Length, Optional, ValidationError
)
from models import ROLES, STATUSES, User, Client


# ──────────────────────────────────────────────
# Authentication forms
# ──────────────────────────────────────────────

class LoginForm(FlaskForm):
    """Login form — accepts username and password."""
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Log In")


class RegisterUserForm(FlaskForm):
    """Admin form to create a new user account."""
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=80)])
    email = EmailField("Email", validators=[DataRequired(), Email()])
    role = SelectField("Role", choices=ROLES, validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField(
        "Confirm Password", validators=[DataRequired(), EqualTo("password")]
    )
    submit = SubmitField("Create User")

    def validate_username(self, field):
        """Ensure the username is not already taken."""
        if User.query.filter_by(username=field.data).first():
            raise ValidationError("Username already exists.")

    def validate_email(self, field):
        """Ensure the email is not already registered."""
        if User.query.filter_by(email=field.data).first():
            raise ValidationError("Email already registered.")


# ──────────────────────────────────────────────
# Client forms
# ──────────────────────────────────────────────

class ClientForm(FlaskForm):
    """Form to create or edit a client."""
    name = StringField("Client Name", validators=[DataRequired(), Length(max=120)])
    contact_email = EmailField("Contact Email", validators=[Optional(), Email()])
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=500)])
    submit = SubmitField("Save Client")

    def __init__(self, original_name=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Store the original name so we can skip uniqueness check on edit
        self.original_name = original_name

    def validate_name(self, field):
        """Ensure client name is unique, unless editing the same record."""
        existing = Client.query.filter_by(name=field.data).first()
        if existing and field.data != self.original_name:
            raise ValidationError("A client with this name already exists.")


# ──────────────────────────────────────────────
# Task forms
# ──────────────────────────────────────────────

# Only non-admin roles are valid task role targets
TASK_ROLES = [r for r in ROLES if r[0] != "admin"]


class TaskForm(FlaskForm):
    """Admin form to create a new task."""
    title = StringField("Task Title", validators=[DataRequired(), Length(max=200)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=1000)])
    client_id = SelectField("Client", coerce=int, validators=[DataRequired()])
    role = SelectField("Required Role", choices=TASK_ROLES, validators=[DataRequired()])
    assigned_to_id = SelectField("Assign To (optional)", coerce=int, validators=[Optional()])
    deadline = DateField("Deadline", validators=[Optional()])
    submit = SubmitField("Create Task")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate client choices dynamically
        self.client_id.choices = [
            (c.id, c.name) for c in Client.query.order_by(Client.name).all()
        ]
        # Populate user choices (non-admin users + a blank option)
        users = User.query.filter(User.role != "admin").order_by(User.username).all()
        self.assigned_to_id.choices = [(0, "— Unassigned —")] + [
            (u.id, f"{u.username} ({u.role})") for u in users
        ]


class TaskEditForm(FlaskForm):
    """Admin form to edit an existing task."""
    title = StringField("Task Title", validators=[DataRequired(), Length(max=200)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=1000)])
    client_id = SelectField("Client", coerce=int, validators=[DataRequired()])
    role = SelectField("Required Role", choices=TASK_ROLES, validators=[DataRequired()])
    assigned_to_id = SelectField("Assign To", coerce=int, validators=[Optional()])
    status = SelectField("Status", choices=STATUSES, validators=[DataRequired()])
    deadline = DateField("Deadline", validators=[Optional()])
    submit = SubmitField("Save Changes")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client_id.choices = [
            (c.id, c.name) for c in Client.query.order_by(Client.name).all()
        ]
        users = User.query.filter(User.role != "admin").order_by(User.username).all()
        self.assigned_to_id.choices = [(0, "— Unassigned —")] + [
            (u.id, f"{u.username} ({u.role})") for u in users
        ]


class StatusUpdateForm(FlaskForm):
    """Simple form for users to update a task's status."""
    status = SelectField("Status", choices=STATUSES, validators=[DataRequired()])
    submit = SubmitField("Update Status")


# ──────────────────────────────────────────────
# Report filter form
# ──────────────────────────────────────────────

class ReportFilterForm(FlaskForm):
    """Form for filtering the report by client, status, and date range."""
    client_id = SelectField("Client", coerce=int, validators=[Optional()])
    status = SelectField("Status", validators=[Optional()])
    date_from = DateField("Date From", validators=[Optional()])
    date_to = DateField("Date To", validators=[Optional()])
    submit = SubmitField("Apply Filter")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client_id.choices = [(0, "All Clients")] + [
            (c.id, c.name) for c in Client.query.order_by(Client.name).all()
        ]
        self.status.choices = [("", "All Statuses")] + list(STATUSES)
