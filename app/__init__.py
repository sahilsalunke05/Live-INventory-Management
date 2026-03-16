from flask import Flask, app
from datetime import timedelta
from config import Config

from .extensions import db, migrate, login_manager, mail
from flask_apscheduler import APScheduler
from datetime import datetime



scheduler = APScheduler()  # single global scheduler

def create_app():
    app = Flask(__name__)

    #  Config 
    app.config.from_object(Config)
    app.config['SECRET_KEY'] = 'super-secret-key'
    app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+pymysql://root:tiger@localhost/supermarket_db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["REMEMBER_COOKIE_DURATION"] = timedelta(hours=1)

    # Email (Gmail app password recommended)
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = "sahil.salunke816@gmail.com"
    app.config['MAIL_PASSWORD'] = "deav qkvb izwc jhhu"
    app.config['MAIL_DEFAULT_SENDER'] = "sahil.salunke816@gmail.com"

    # Optional app-level knobs for the job
    app.config.setdefault("LOW_STOCK_THRESHOLD", 10)
    app.config.setdefault("LOW_STOCK_RECIPIENTS", ["admin@supermarket.com"])

    #  Extensions 
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    scheduler.init_app(app)

    # Login manager settings
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "info"

    #  Blueprints 
    from .blueprints.main.routes import main_bp
    from .blueprints.auth.routes import auth_bp
    from .blueprints.staff.routes import staff_bp
    from .blueprints.manager.routes import manager_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(manager_bp)

    #  Default Accounts Setup 
    from werkzeug.security import generate_password_hash
    with app.app_context():
        from .models import User

        manager = User.query.filter_by(role="manager").first()
        if not manager:
            manager = User(
                username="admin",
                email="admin@supermarket.com",
                password=generate_password_hash("admin123", method="sha256"),
                role="manager",
            )
            db.session.add(manager)
            db.session.commit()
            print("\n✅ Default Manager created: admin / admin123\n")

        staff = User.query.filter_by(role="staff").first()
        if not staff:
            staff = User(
                username="staff",
                email="staff@supermarket.com",
                password=generate_password_hash("staff123", method="sha256"),
                role="staff",
            )
            db.session.add(staff)
            db.session.commit()
            print("✅ Default Staff created: staff / staff123\n")

        #  Scheduler Job Registration 
        # Import INSIDE app context to avoid circular import issues
        from .tasks import check_low_stock

        

        # Run at local midnight (Asia/Kolkata)
        scheduler.add_job(
            id="low_stock_job",
            func=check_low_stock,
            trigger="cron",
            hour=0,
            minute=0,
            timezone="Asia/Kolkata",
            replace_existing=True,
        )

    scheduler.start()
    @app.context_processor
    def inject_current_year():
        return {"current_year": datetime.utcnow().year}
    return app
