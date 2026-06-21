"""
blueprints/tasks.py — Task routes for regular (non-admin) users.
Users can view their assigned tasks and update statuses.
"""

from flask import Blueprint, render_template, redirect, url_for, flash, abort, request
from flask_login import login_required, current_user
from models import db, Task, Comment, ActivityLog, STATUSES
from forms import StatusUpdateForm
from activity import log_status_change

tasks_bp = Blueprint("tasks", __name__, url_prefix="/tasks")


@tasks_bp.route("/")
@login_required
def list_tasks():
    """
    Show tasks for the current user.
    - Admins see all tasks with optional filters.
    - Regular users see only their assigned tasks.
    """
    status_filter = request.args.get("status")
    role_filter = request.args.get("role")

    if current_user.is_admin:
        query = Task.query
    else:
        query = Task.query.filter_by(assigned_to_id=current_user.id)

    if status_filter:
        query = query.filter_by(status=status_filter)
    if role_filter:
        query = query.filter_by(role=role_filter)

    tasks = query.order_by(Task.deadline.asc().nullslast(), Task.created_at.desc()).all()

    return render_template(
        "tasks/list.html",
        tasks=tasks,
        statuses=STATUSES,
        selected_status=status_filter,
        selected_role=role_filter,
    )


@tasks_bp.route("/<int:task_id>")
@login_required
def task_detail(task_id):
    """Show detail for a single task."""
    task = Task.query.get_or_404(task_id)

    # Regular users can only view their own tasks
    if not current_user.is_admin and task.assigned_to_id != current_user.id:
        abort(403)

    form = StatusUpdateForm(status=task.status)
    can_comment = current_user.is_admin or task.assigned_to_id == current_user.id
    comments = task.comments.order_by(Comment.created_at.asc()).all()
    activity = task.activity_log.order_by(ActivityLog.created_at.asc()).all()
    return render_template("tasks/detail.html", task=task, form=form,
                           comments=comments, can_comment=can_comment,
                           activity=activity)


@tasks_bp.route("/<int:task_id>/update-status", methods=["POST"])
@login_required
def update_status(task_id):
    """Update the status of a task (assigned user or admin only)."""
    task = Task.query.get_or_404(task_id)

    # Only the assigned user or an admin can change status
    if not current_user.is_admin and task.assigned_to_id != current_user.id:
        abort(403)

    form = StatusUpdateForm()
    if form.validate_on_submit():
        old_status = task.status
        task.status = form.status.data
        db.session.commit()
        log_status_change(task, old_status, task.status, actor_id=current_user.id)
        flash(f"Task status updated to '{task.status}'.", "success")
    else:
        flash("Invalid status value.", "danger")

    return redirect(url_for("tasks.task_detail", task_id=task.id))
