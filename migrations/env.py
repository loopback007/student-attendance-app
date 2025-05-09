# migrations/env.py
from logging.config import fileConfig

from sqlalchemy import engine_from_config # Retain for potential offline use or other contexts
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# --- Flask-Migrate specific setup ---
# Import the db object from your Flask application
from app import db # Assuming your Flask-SQLAlchemy db object is in 'app'
# Ensure all your models are imported so their metadata is registered with db.metadata
# For example, if your models are in app.models:
from app.models import * # This will import all your models
target_metadata = db.metadata
# --- End Flask-Migrate specific setup ---


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Configure the Alembic context with the URL from the Flask app.
    # This makes sure Alembic knows the database URL for its operations.
    # The .replace('%', '%%') is to escape any literal '%' signs in the URL,
    # as configparser (used by Alembic) might interpret them.
    db_url_str = str(db.engine.url).replace('%', '%%')
    config.set_main_option('sqlalchemy.url', db_url_str)

    # The connectable should be the engine from our Flask app
    connectable = db.engine

    with connectable.connect() as connection:
        # Determine if we are using SQLite for batch mode
        # Check the dialect of the engine being used.
        is_sqlite = connectable.dialect.name == 'sqlite'

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=is_sqlite,  # Enable batch mode for SQLite
            # compare_type=True # Uncomment if you want to detect column type changes
            # include_object=include_object, # If you have custom filtering for tables
            # process_revision_directives=process_revision_directives, # For custom revision generation
        )

        with context.begin_transaction():
            context.run_migrations()

# This section handles how migrations are run (offline or online)
if context.is_offline_mode():
    # For offline mode, Alembic needs the URL directly.
    # This is a simplified example; your actual offline setup might differ.
    db_url_str_offline = str(db.engine.url).replace('%', '%%')
    context.configure(
        url=db_url_str_offline, 
        target_metadata=target_metadata,
        literal_binds=True, # Usually True for offline script generation
        dialect_opts={"paramstyle": "named"},
        render_as_batch=db_url_str_offline.startswith('sqlite:') # Enable batch for SQLite in offline too
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    run_migrations_online()
