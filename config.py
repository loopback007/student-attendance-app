# config.py

import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-default-secret-key-change-me'

    # Database configuration
    # Check if running inside Docker (a simple way is to check for an env var set by Docker/Compose)
    # OR, more reliably, allow DATABASE_URL to be set from environment for full flexibility.
    if os.environ.get('DOCKER_CONTAINER'): # You would set DOCKER_CONTAINER=true in docker-compose.yml app environment
        # Path inside the Docker container, using the named volume mount point
        SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
            'sqlite:///' + os.path.join('/app', 'data', 'app.db')
    else:
        # Original path for local development (outside Docker)
        SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
            'sqlite:///' + os.path.join(basedir, 'app.db')
            
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    DEFAULT_ADMIN_USERNAME = os.environ.get('DEFAULT_ADMIN_USERNAME') or 'admin'
    DEFAULT_ADMIN_PASSWORD = os.environ.get('DEFAULT_ADMIN_PASSWORD') or 'adminpass'
    DEFAULT_ADMIN_EMAIL = os.environ.get('DEFAULT_ADMIN_EMAIL') or 'admin@example.com'

    # Optional: Define UPLOAD_FOLDER if you plan to handle file uploads and save them
    # UPLOAD_FOLDER = os.path.join(basedir, 'uploads') # For local
    # Or for Docker: UPLOAD_FOLDER = '/app/uploads_volume' (and mount a volume)

class DevelopmentConfig(Config):
    DEBUG = True
    # SQLALCHEMY_ECHO = True # Useful for debugging SQL queries

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:' 
    WTF_CSRF_ENABLED = False 

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    # In production, DATABASE_URL and SECRET_KEY should DEFINITELY be set via environment variables.
    # The Docker_CONTAINER check above is one way to handle dev vs. containerized paths.

config_by_name = dict(
    development=DevelopmentConfig,
    testing=TestingConfig,
    production=ProductionConfig,
    default=DevelopmentConfig
)

def get_config_name():
    return os.getenv('FLASK_CONFIG') or 'default'
