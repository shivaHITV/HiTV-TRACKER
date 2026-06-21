"""
app.py — Application factory and entry point for HiTV Production Manager.
Creates the Flask app, registers extensions, blueprints, and seeds demo data.
"""

import os
from flask import Flask, render_template
from models import db, User, Client, Task, Notification, Comment, ActivityLog
from extensions import login_manager, mail
from config import config_map


def create_app(config_name: str = "default") -> Flask:
    """
    Application factory.
    Creates and configures a Flask instance.
    """
    app = Flask(__name__)
    app.config.from_object(config_map[config_name])

    # ── Initialise extensions ──────────────────────────────────────
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)

    # ── User loader callback for Flask-Login ───────────────────────
    @login_manager.user_loader
    def load_user(user_id: str):
        return User.query.get(int(user_id))

    # ── Context processor: unread notification count ───────────────
    # Injects `unread_count` into every template automatically.
    from flask_login import current_user

    @app.context_processor
    def inject_unread_count():
        if current_user.is_authenticated:
            count = Notification.query.filter_by(
                user_id=current_user.id, is_read=False
            ).count()
            return {"unread_notif_count": count}
        return {"unread_notif_count": 0}

    # ── Register blueprints ────────────────────────────────────────
    from blueprints.auth import auth_bp
    from blueprints.main import main_bp
    from blueprints.admin import admin_bp
    from blueprints.tasks import tasks_bp
    from blueprints.reports import reports_bp
    from blueprints.notifications import notifications_bp
    from blueprints.comments import comments_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(comments_bp)

    # ── Custom error pages ─────────────────────────────────────────
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/500.html"), 500

    # ── Create tables and seed demo data ──────────────────────────
    with app.app_context():
        db.create_all()
        _seed_demo_data()

    return app


def _seed_demo_data():
    """
    Insert demo admin + sample users, clients, and tasks on first run.
    Only runs if the database is empty (no users exist yet).
    """
    if User.query.first():
        return  # Already seeded

    # ── Admin user ────────────────────────────────────────────────
    admin = User(username="admin", email="admin@hitv.com", role="admin")
    admin.set_password("admin123")

    # ── Sample crew users ─────────────────────────────────────────
    videographer = User(username="alex_video", email="alex@hitv.com", role="videographer")
    videographer.set_password("pass1234")

    editor = User(username="morgan_edit", email="morgan@hitv.com", role="editor")
    editor.set_password("pass1234")

    marketer = User(username="sam_market", email="sam@hitv.com", role="marketer")
    marketer.set_password("pass1234")

    db.session.add_all([admin, videographer, editor, marketer])
    db.session.flush()  # Assign IDs before creating related records

    # ── Sample clients ────────────────────────────────────────────
    client_a = Client(name="Acme Corp", contact_email="contact@acme.com",
                      notes="Long-term corporate client.")
    client_b = Client(name="Nova Brands", contact_email="hello@novabrands.com",
                      notes="Fashion and lifestyle brand.")
    client_c = Client(name="TechVision", contact_email="info@techvision.io",
                      notes="Tech startup, product launch campaign.")
    db.session.add_all([client_a, client_b, client_c])
    db.session.flush()

    # ── Sample tasks ──────────────────────────────────────────────
    from datetime import date, timedelta
    today = date.today()

    tasks = [
        Task(title="Shoot product launch reel", client_id=client_a.id, role="videographer",
             assigned_to_id=videographer.id, created_by_id=admin.id,
             status="ongoing", deadline=today + timedelta(days=5),
             description="Capture the Acme product launch event. 4K, b-roll included."),
        Task(title="Edit brand story video", client_id=client_b.id, role="editor",
             assigned_to_id=editor.id, created_by_id=admin.id,
             status="pending", deadline=today + timedelta(days=10),
             description="Cut the raw footage from Nova Brands shoot into a 90-second brand video."),
        Task(title="Social media campaign launch", client_id=client_b.id, role="marketer",
             assigned_to_id=marketer.id, created_by_id=admin.id,
             status="pending", deadline=today + timedelta(days=7),
             description="Create Instagram and LinkedIn posts for the Nova Brands spring campaign."),
        Task(title="TechVision interview shoot", client_id=client_c.id, role="videographer",
             assigned_to_id=videographer.id, created_by_id=admin.id,
             status="completed", deadline=today - timedelta(days=3),
             description="CEO interview for product demo page."),
        Task(title="Edit TechVision explainer", client_id=client_c.id, role="editor",
             assigned_to_id=editor.id, created_by_id=admin.id,
             status="ongoing", deadline=today + timedelta(days=2),
             description="Animate and cut the product explainer video."),
        Task(title="Acme email newsletter", client_id=client_a.id, role="marketer",
             assigned_to_id=marketer.id, created_by_id=admin.id,
             status="completed", deadline=today - timedelta(days=10),
             description="Monthly newsletter — highlight the new product line."),
    ]
    db.session.add_all(tasks)
    db.session.flush()

    # ── Seed demo notifications for crew users ─────────────────────
    # (mirrors what would have been auto-created by notify.py in production)
    demo_notifs = [
        Notification(user_id=videographer.id, notif_type="assigned", task_id=tasks[0].id,
                     message=f'You\'ve been assigned: "{tasks[0].title}" for {client_a.name} — due {tasks[0].deadline.strftime("%b %d, %Y")}.'),
        Notification(user_id=editor.id, notif_type="assigned", task_id=tasks[1].id,
                     message=f'You\'ve been assigned: "{tasks[1].title}" for {client_b.name} — due {tasks[1].deadline.strftime("%b %d, %Y")}.'),
        Notification(user_id=marketer.id, notif_type="assigned", task_id=tasks[2].id,
                     message=f'You\'ve been assigned: "{tasks[2].title}" for {client_b.name} — due {tasks[2].deadline.strftime("%b %d, %Y")}.'),
        Notification(user_id=editor.id, notif_type="deadline", task_id=tasks[4].id,
                     message=f'⏰ Deadline reminder: "{tasks[4].title}" for {client_c.name} is due in 2 days ({tasks[4].deadline.strftime("%b %d, %Y")}).'),
    ]
    db.session.add_all(demo_notifs)
    db.session.commit()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app = create_app("development" if debug else "production")
    app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=False)
