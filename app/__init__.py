# app/__init__.py

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect # Import CSRFProtect
from datetime import datetime # For the 'now' context processor
import logging #added for flask logging
from logging.handlers import RotatingFileHandler #added for flask logging
import os

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

    app = Flask(__name__, instance_relative_config=True) # IMPORTANT
    selected_config_object = config_by_name[config_name] 
    app.config.from_object(selected_config_object) 
    # Check if the selected config class/object itself has an init_app method
    if hasattr(selected_config_object, 'init_app') and callable(getattr(selected_config_object, 'init_app')):
        selected_config_object.init_app(app)
        
    # --- Diagnostic Prints (check these in Docker logs) ---
    print(f"INFO: [create_app] Flask App Name: {app.name}")
    print(f"INFO: [create_app] Flask Root Path: {app.root_path}")
    print(f"INFO: [create_app] Flask Instance Path: {app.instance_path}") # CRITICAL
    print(f"INFO: [create_app] app.debug state: {app.debug}")
    print(f"INFO: [create_app] app.testing state: {app.testing}")
    # --- End Diagnostic Prints ---

    # Ensure SECRET_KEY is set for CSRF protection to work
    if not app.config.get('SECRET_KEY'):
        raise ValueError("SECRET_KEY is not set in the application configuration!")
        
    # --- LOGGING CONFIGURATION ---
    # (Your logging setup code - ensure it's correctly placed and indented)
    # Based on your docker-compose, FLASK_DEBUG=0, so this block should run:
    # if not app.debug and not app.testing: # You can keep this condition
    print(f"INFO: [Logging] app.debug is {app.debug}, app.testing is {app.testing}. Entering file logging setup based on this.")
    
    log_directory = os.path.join(app.instance_path, 'logs')
    print(f"INFO: [Logging] Determined log directory path: {log_directory}")

    if not os.path.exists(app.instance_path):
        try:
            os.makedirs(app.instance_path)
            print(f"INFO: [Logging] Instance directory created at: {app.instance_path}")
        except OSError as e:
            print(f"ERROR: [Logging] Failed to create instance directory {app.instance_path}: {e}")
    
    if not os.path.exists(log_directory):
        try:
            os.makedirs(log_directory)
            print(f"INFO: [Logging] Log directory created at: {log_directory}")
        except OSError as e:
            print(f"ERROR: [Logging] Failed to create log directory {log_directory}: {e}")
    
    if os.path.exists(log_directory) and os.access(log_directory, os.W_OK):
        log_file_path = os.path.join(log_directory, 'attendance_app.log')
        print(f"INFO: [Logging] Attempting to set up file handler for: {log_file_path}")
        
        file_handler = RotatingFileHandler(log_file_path, maxBytes=102400, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)

        if not any(isinstance(handler, RotatingFileHandler) and handler.baseFilename == file_handler.baseFilename for handler in app.logger.handlers):
            app.logger.addHandler(file_handler)
            print("INFO: [Logging] RotatingFileHandler added to app.logger.")
        else:
            print("INFO: [Logging] RotatingFileHandler already present for this file.")

        app.logger.setLevel(logging.INFO)
        app.logger.info('Attendance App startup - File logging active and initialized.')
    else:
        print(f"WARNING: [Logging] Log directory {log_directory} does NOT exist or is NOT writable. File logging SKIPPED.")
    # --- END OF LOGGING CONFIGURATION ---

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
