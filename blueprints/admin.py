"""
blueprints/admin.py — Admin-only routes for managing users, clients, and tasks.
All routes require login AND admin role.
Fires in-app notifications (and optional email) on task creation and reassignment.
"""

from flask import Blueprint, render_template, redirect, url_for, flash, abort, request
from flask_login import login_required, current_user
from models import db, User, Client, Task, ROLES
from forms import RegisterUserForm, ClientForm, TaskForm, TaskEditForm
from activity import log_task_created, log_reassignment, log_field_changes

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def require_admin():
    """Abort with 403 if the current user is not an admin."""
    if not current_user.is_admin:
        abort(403)


# ──────────────────────────────────────────────
# User management
# ──────────────────────────────────────────────

@admin_bp.route("/users")
@login_required
def users():
    """List all users."""
    require_admin()
    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", users=all_users, roles=ROLES)


@admin_bp.route("/users/create", methods=["GET", "POST"])
@login_required
def create_user():
    """Create a new user account."""
    require_admin()
    form = RegisterUserForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data.strip(),
            email=form.email.data.strip().lower(),
            role=form.role.data,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash(f"User '{user.username}' created successfully.", "success")
        return redirect(url_for("admin.users"))
    return render_template("admin/create_user.html", form=form)


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
def delete_user(user_id):
    """Delete a user (cannot delete yourself)."""
    require_admin()
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("You cannot delete your own account.", "danger")
        return redirect(url_for("admin.users"))
    db.session.delete(user)
    db.session.commit()
    flash(f"User '{user.username}' deleted.", "info")
    return redirect(url_for("admin.users"))


# ──────────────────────────────────────────────
# Client management
# ──────────────────────────────────────────────

@admin_bp.route("/clients")
@login_required
def clients():
    """List all clients."""
    require_admin()
    all_clients = Client.query.order_by(Client.name).all()
    return render_template("admin/clients.html", clients=all_clients)


@admin_bp.route("/clients/create", methods=["GET", "POST"])
@login_required
def create_client():
    """Create a new client."""
    require_admin()
    form = ClientForm()
    if form.validate_on_submit():
        client = Client(
            name=form.name.data.strip(),
            contact_email=form.contact_email.data.strip() if form.contact_email.data else None,
            notes=form.notes.data,
        )
        db.session.add(client)
        db.session.commit()
        flash(f"Client '{client.name}' created.", "success")
        return redirect(url_for("admin.clients"))
    return render_template("admin/create_client.html", form=form)


@admin_bp.route("/clients/<int:client_id>/edit", methods=["GET", "POST"])
@login_required
def edit_client(client_id):
    """Edit an existing client."""
    require_admin()
    client = Client.query.get_or_404(client_id)
    form = ClientForm(original_name=client.name, obj=client)
    if form.validate_on_submit():
        client.name = form.name.data.strip()
        client.contact_email = form.contact_email.data.strip() if form.contact_email.data else None
        client.notes = form.notes.data
        db.session.commit()
        flash("Client updated.", "success")
        return redirect(url_for("admin.clients"))
    return render_template("admin/create_client.html", form=form, editing=True, client=client)


@admin_bp.route("/clients/<int:client_id>/delete", methods=["POST"])
@login_required
def delete_client(client_id):
    """Delete a client (only if no tasks are linked)."""
    require_admin()
    client = Client.query.get_or_404(client_id)
    if client.tasks.count() > 0:
        flash("Cannot delete a client that has tasks. Remove tasks first.", "danger")
        return redirect(url_for("admin.clients"))
    db.session.delete(client)
    db.session.commit()
    flash(f"Client '{client.name}' deleted.", "info")
    return redirect(url_for("admin.clients"))


# ──────────────────────────────────────────────
# Task management (admin view)
# ──────────────────────────────────────────────

@admin_bp.route("/tasks")
@login_required
def tasks():
    """List all tasks with filter controls."""
    require_admin()
    client_id = request.args.get("client_id", type=int)
    status = request.args.get("status")
    role = request.args.get("role")

    query = Task.query
    if client_id:
        query = query.filter_by(client_id=client_id)
    if status:
        query = query.filter_by(status=status)
    if role:
        query = query.filter_by(role=role)

    all_tasks = query.order_by(Task.created_at.desc()).all()
    all_clients = Client.query.order_by(Client.name).all()
    return render_template(
        "admin/tasks.html",
        tasks=all_tasks,
        clients=all_clients,
        selected_client=client_id,
        selected_status=status,
        selected_role=role,
    )


@admin_bp.route("/tasks/create", methods=["GET", "POST"])
@login_required
def create_task():
    """Create a new task and notify the assignee."""
    require_admin()
    form = TaskForm()
    if form.validate_on_submit():
        assigned_id = form.assigned_to_id.data if form.assigned_to_id.data != 0 else None
        task = Task(
            title=form.title.data.strip(),
            description=form.description.data,
            client_id=form.client_id.data,
            role=form.role.data,
            assigned_to_id=assigned_id,
            deadline=form.deadline.data,
            created_by_id=current_user.id,
            status="pending",
        )
        db.session.add(task)
        db.session.commit()

        # Activity log — task created
        log_task_created(task, actor_id=current_user.id)

        # Fire assignment notification + optional email
        if assigned_id:
            from notify import notify_task_assigned
            notify_task_assigned(task)

        flash(f"Task '{task.title}' created.", "success")
        return redirect(url_for("admin.tasks"))
    return render_template("admin/create_task.html", form=form)


@admin_bp.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
@login_required
def edit_task(task_id):
    """Edit an existing task; notify if the assignee changed."""
    require_admin()
    task = Task.query.get_or_404(task_id)
    old_assignee_id = task.assigned_to_id  # Remember before any changes

    form = TaskEditForm(obj=task)
    if form.validate_on_submit():
        # Capture old values before mutation
        old_title = task.title
        old_description = task.description
        old_role = task.role
        old_deadline = task.deadline
        old_status = task.status

        task.title = form.title.data.strip()
        task.description = form.description.data
        task.client_id = form.client_id.data
        task.role = form.role.data
        new_assignee_id = form.assigned_to_id.data if form.assigned_to_id.data != 0 else None
        task.assigned_to_id = new_assignee_id
        task.status = form.status.data
        task.deadline = form.deadline.data
        db.session.commit()

        # Activity log — field changes
        log_field_changes(task, {
            "title":       (old_title, task.title),
            "description": (old_description, task.description),
            "role":        (old_role, task.role),
            "deadline":    (str(old_deadline) if old_deadline else None,
                            str(task.deadline) if task.deadline else None),
        }, actor_id=current_user.id)

        # Activity log — status change
        if old_status != task.status:
            from activity import log_status_change
            log_status_change(task, old_status, task.status, actor_id=current_user.id)

        # Activity log + notification on assignment change
        if new_assignee_id != old_assignee_id:
            log_reassignment(task, old_assignee_id, new_assignee_id, actor_id=current_user.id)
            if new_assignee_id:
                from notify import notify_task_reassigned
                notify_task_reassigned(task, old_assignee_id)

        flash("Task updated.", "success")
        return redirect(url_for("admin.tasks"))

    # Pre-select current assignee
    if task.assigned_to_id:
        form.assigned_to_id.data = task.assigned_to_id
    return render_template("admin/create_task.html", form=form, editing=True, task=task)


@admin_bp.route("/tasks/<int:task_id>/delete", methods=["POST"])
@login_required
def delete_task(task_id):
    """Delete a task."""
    require_admin()
    task = Task.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    flash("Task deleted.", "info")
    return redirect(url_for("admin.tasks"))
