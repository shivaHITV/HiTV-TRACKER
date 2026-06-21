"""
blueprints/comments.py — Task comment routes.
Any authenticated user who can view a task can add a comment.
Authors and admins can delete or edit their own comments.
"""

from flask import Blueprint, redirect, url_for, flash, abort, request, render_template
from flask_login import login_required, current_user
from models import db, Task, Comment

comments_bp = Blueprint("comments", __name__, url_prefix="/comments")


def _can_view_task(task) -> bool:
    """Return True if the current user is allowed to see this task."""
    return current_user.is_admin or task.assigned_to_id == current_user.id


# ──────────────────────────────────────────────
# Add a comment
# ──────────────────────────────────────────────

@comments_bp.route("/task/<int:task_id>/add", methods=["POST"])
@login_required
def add_comment(task_id):
    """Post a new comment on a task."""
    task = Task.query.get_or_404(task_id)

    if not _can_view_task(task):
        abort(403)

    body = request.form.get("body", "").strip()
    if not body:
        flash("Comment cannot be empty.", "warning")
        return redirect(url_for("tasks.task_detail", task_id=task_id))

    if len(body) > 2000:
        flash("Comment is too long (max 2000 characters).", "warning")
        return redirect(url_for("tasks.task_detail", task_id=task_id))

    comment = Comment(task_id=task_id, author_id=current_user.id, body=body)
    db.session.add(comment)
    db.session.commit()

    # Notify the admin and assignee (excluding the commenter) about the new comment
    _notify_new_comment(task, comment)

    flash("Comment added.", "success")
    return redirect(url_for("tasks.task_detail", task_id=task_id) + "#comments")


# ──────────────────────────────────────────────
# Edit a comment
# ──────────────────────────────────────────────

@comments_bp.route("/<int:comment_id>/edit", methods=["GET", "POST"])
@login_required
def edit_comment(comment_id):
    """Edit an existing comment (author or admin only)."""
    comment = Comment.query.get_or_404(comment_id)

    # Only the author or an admin may edit
    if comment.author_id != current_user.id and not current_user.is_admin:
        abort(403)

    if request.method == "POST":
        body = request.form.get("body", "").strip()
        if not body:
            flash("Comment cannot be empty.", "warning")
        elif len(body) > 2000:
            flash("Comment is too long (max 2000 characters).", "warning")
        else:
            comment.body = body
            db.session.commit()
            flash("Comment updated.", "success")
            return redirect(url_for("tasks.task_detail", task_id=comment.task_id) + "#comments")

    return render_template("tasks/edit_comment.html", comment=comment)


# ──────────────────────────────────────────────
# Delete a comment
# ──────────────────────────────────────────────

@comments_bp.route("/<int:comment_id>/delete", methods=["POST"])
@login_required
def delete_comment(comment_id):
    """Delete a comment (author or admin only)."""
    comment = Comment.query.get_or_404(comment_id)

    if comment.author_id != current_user.id and not current_user.is_admin:
        abort(403)

    task_id = comment.task_id
    db.session.delete(comment)
    db.session.commit()
    flash("Comment deleted.", "info")
    return redirect(url_for("tasks.task_detail", task_id=task_id) + "#comments")


# ──────────────────────────────────────────────
# Notify on new comment
# ──────────────────────────────────────────────

def _notify_new_comment(task, comment) -> None:
    """
    Create in-app notifications for task participants when a comment is added.
    - If the commenter is the assignee → notify the admin(s) who created the task.
    - If the commenter is an admin → notify the assignee.
    - Skips notifying the commenter themselves.
    """
    from models import Notification, User

    targets = set()

    # Always include the task creator (admin who made the task)
    if task.created_by_id and task.created_by_id != current_user.id:
        targets.add(task.created_by_id)

    # Include the assignee if they're not the commenter
    if task.assigned_to_id and task.assigned_to_id != current_user.id:
        targets.add(task.assigned_to_id)

    preview = comment.body[:80] + ("..." if len(comment.body) > 80 else "")
    message = (
        f'💬 {current_user.username} commented on "{task.title}": {preview}'
    )

    for user_id in targets:
        notif = Notification(
            user_id=user_id,
            notif_type="status",   # reuse "status" type for comment notifications
            task_id=task.id,
            message=message,
        )
        db.session.add(notif)

    if targets:
        db.session.commit()
