import os
import logging
from flask import Flask, g
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect
from models import db, User, Notification
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

APP_VERSION = '2.1.0'   # bump this to force Railway to rebuild & confirm version in logs


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    db.init_app(app)

    # CSRF protection
    csrf = CSRFProtect(app)
    # Also expose csrf_token() in Jinja2 (CSRFProtect does this automatically,
    # but keep the explicit assignment for safety)
    from flask_wtf.csrf import generate_csrf
    app.jinja_env.globals['csrf_token'] = generate_csrf

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Παρακαλώ συνδεθείτε για πρόσβαση.'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        # Use Session.get() — Query.get() is deprecated in SQLAlchemy 2.0
        return db.session.get(User, int(user_id))

    # Inject notification count into all templates
    @app.context_processor
    def inject_notifications():
        if current_user.is_authenticated:
            unread = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
            notifications = Notification.query.filter_by(
                user_id=current_user.id, is_read=False
            ).order_by(Notification.created_at.desc()).limit(8).all()
        else:
            unread = 0
            notifications = []
        return dict(unread_notifications=unread, notifications=notifications)

    # Register blueprints
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.tenders import tenders_bp
    from routes.projects import projects_bp
    from routes.invoices import invoices_bp
    from routes.documents import documents_bp
    from routes.hr import hr_bp
    from routes.equipment import equipment_bp
    from routes.vehicles import vehicles_bp
    from routes.accounting import accounting_bp
    from routes.legal import legal_bp
    from routes.worker import worker_bp
    from routes.recurring import recurring_bp
    from routes.cash import cash_bp
    from routes.insurance import insurance_bp
    from routes.inventory import inventory_bp
    from routes.payroll import payroll_bp
    from routes.quotes import quotes_bp
    from routes.safety import safety_bp
    from routes.reports import reports_bp
    from routes.calendar import calendar_bp
    from routes.supplies import supplies_bp
    from routes.subcontractors import subcontractors_bp
    from routes.scaffolding import scaffolding_bp
    from routes.design import design_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(tenders_bp, url_prefix='/tenders')
    app.register_blueprint(projects_bp, url_prefix='/projects')
    app.register_blueprint(invoices_bp, url_prefix='/invoices')
    app.register_blueprint(documents_bp, url_prefix='/documents')
    app.register_blueprint(hr_bp, url_prefix='/hr')
    app.register_blueprint(equipment_bp, url_prefix='/equipment')
    app.register_blueprint(vehicles_bp, url_prefix='/vehicles')
    app.register_blueprint(accounting_bp, url_prefix='/accounting')
    app.register_blueprint(legal_bp, url_prefix='/legal')
    app.register_blueprint(worker_bp, url_prefix='/worker')
    app.register_blueprint(recurring_bp, url_prefix='/recurring')
    app.register_blueprint(cash_bp, url_prefix='/cash')
    app.register_blueprint(insurance_bp, url_prefix='/insurance')
    app.register_blueprint(inventory_bp, url_prefix='/inventory')
    app.register_blueprint(payroll_bp, url_prefix='/payroll')
    app.register_blueprint(quotes_bp, url_prefix='/quotes')
    app.register_blueprint(safety_bp, url_prefix='/safety')
    app.register_blueprint(reports_bp, url_prefix='/reports')
    app.register_blueprint(calendar_bp, url_prefix='/calendar')
    app.register_blueprint(supplies_bp, url_prefix='/supplies')
    app.register_blueprint(subcontractors_bp, url_prefix='/subcontractors')
    app.register_blueprint(scaffolding_bp, url_prefix='/scaffolding')
    app.register_blueprint(design_bp, url_prefix='/design')

    # Notification mark-as-read
    from flask import request as _req, jsonify as _jsonify
    from flask_login import login_required as _login_required

    @app.route('/notifications/read', methods=['POST'])
    @_login_required
    def mark_notifications_read():
        Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
        db.session.commit()
        return _jsonify({'ok': True})

    @app.route('/notifications/<int:nid>/read', methods=['POST'])
    @_login_required
    def mark_one_read(nid):
        n = Notification.query.filter_by(id=nid, user_id=current_user.id).first()
        if n:
            n.is_read = True
            db.session.commit()
        return _jsonify({'ok': True})

    with app.app_context():
        logger.info('ART ERP v%s — starting up', APP_VERSION)
        db.create_all()
        _run_migrations()
        _create_default_admin()

    return app


def _run_migrations():
    """Add columns introduced after initial DB creation (PostgreSQL + SQLite safe)."""
    from sqlalchemy import text
    migrations = [
        "ALTER TABLE employees ADD COLUMN annual_leave_days INTEGER DEFAULT 20",
        "ALTER TABLE employees ADD COLUMN contract_file_path VARCHAR(600)",
        "ALTER TABLE employees ADD COLUMN contract_file_name VARCHAR(400)",
    ]
    for sql in migrations:
        try:
            with db.engine.begin() as conn:   # own transaction per statement
                conn.execute(text(sql))
        except Exception as e:
            # Column already exists — safe to ignore. Log at DEBUG for visibility.
            logger.debug('Migration skipped (likely already applied): %s — %s', sql[:60], e)


def _create_default_admin():
    try:
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                email='admin@artrestoration.gr',
                full_name='Χρήστος Λιούγκος',
                role='admin',
            )
            admin.set_password('ArtRestore2026!')
            db.session.add(admin)
            db.session.commit()
    except Exception as e:
        # Race condition between gunicorn workers on first deploy — safe to ignore
        db.session.rollback()
        logger.debug('Admin creation skipped (likely race condition): %s', e)


if __name__ == '__main__':
    app = create_app()
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=True, host='0.0.0.0', port=port)
