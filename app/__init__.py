# app/__init__.py

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect # Import CSRFProtect
from datetime import datetime # For the 'now' context processor

from config import config_by_name, get_config_name

# Initialize extensions (but don't configure them with an app instance yet)
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
csrf = CSRFProtect() # Create an instance of CSRFProtect

# LoginManager configuration
login_manager.login_view = 'auth.login' # Route to redirect to for login
login_manager.login_message = 'Please log in to access this page.' # Flash message
login_manager.login_message_category = 'info' # Flash message category

def create_app(config_name=None):
    """
    Application factory function.
    Creates and configures the Flask application.
    """
    if config_name is None:
        config_name = get_config_name() # Gets FLASK_CONFIG or 'default'

    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    # Ensure SECRET_KEY is set for CSRF protection to work
    if not app.config.get('SECRET_KEY'):
        raise ValueError("SECRET_KEY is not set in the application configuration!")

    # Initialize Flask extensions with the app instance
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db) # Initialize Flask-Migrate
    csrf.init_app(app) # Initialize CSRFProtect with the app

    # Import and register blueprints
    from .auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/auth')

    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from .admin import admin as admin_blueprint
    app.register_blueprint(admin_blueprint, url_prefix='/admin')

    from .teacher import teacher as teacher_blueprint
    app.register_blueprint(teacher_blueprint, url_prefix='/teacher')

    from .staff import staff as staff_blueprint
    app.register_blueprint(staff_blueprint, url_prefix='/staff')
    
    # Context processor to make 'now' available in all templates for the year in footer
    @app.context_processor
    def inject_now():
        return {'now': datetime.utcnow}

    return app
