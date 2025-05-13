# run.py

import os
from app import create_app, db # Import create_app factory and db instance
# Import all models and enums that you want available in flask shell
#from app.models import User, UserRole, Subject, SubjectClass, Student, Attendance, AttendanceStatus, enrollments 
from app.models import User, UserRole, Subject, SubjectClass, Student, Attendance, enrollments, ATTENDANCE_STATUS_CHOICES # Optionally import the new list
from flask_migrate import Migrate 

# Get the configuration name from environment variable or use default
config_name = os.getenv('FLASK_CONFIG') or 'default'
app = create_app(config_name)

@app.cli.command("init_db")
def init_db_command():
    """Creates the database tables if they don't exist based on models.
    For full schema management, use Flask-Migrate:
    flask db init (once per project)
    flask db migrate -m "description"
    flask db upgrade
    """
    db.create_all()
    print("Initialized the database (created tables if they didn't exist).")
    print("For robust schema management, please use Flask-Migrate.")

@app.cli.command("create_admin")
def create_admin_command():
    """Creates the default admin/superuser."""
    from werkzeug.security import generate_password_hash # Keep import local to command

    username = app.config.get('DEFAULT_ADMIN_USERNAME')
    email = app.config.get('DEFAULT_ADMIN_EMAIL')
    password = app.config.get('DEFAULT_ADMIN_PASSWORD')

    if not all([username, email, password]):
        print("Default admin credentials not fully set in config. Aborting.")
        return

    if User.query.filter_by(username=username).first():
        print(f"Admin user '{username}' already exists.")
        return
    
    if User.query.filter_by(email=email).first():
        print(f"User with email '{email}' already exists.")
        return

    admin_user = User(
        username=username,
        email=email,
        first_name="Default",
        last_name="Admin",
        role=UserRole.SUPERUSER, 
        is_active=True
    )
    admin_user.set_password(password) 

    try:
        db.session.add(admin_user)
        db.session.commit()
        print(f"Admin user '{username}' created successfully with SUPERUSER role.")
    except Exception as e:
        db.session.rollback()
        print(f"Error creating admin user: {e}")

# This makes these items available in 'flask shell' without explicit imports
@app.shell_context_processor
def make_shell_context():
    return {
        'db': db,
        'User': User,
        'UserRole': UserRole, # Enum for user roles
        'Subject': Subject,
        'SubjectClass': SubjectClass,
        'Student': Student,
        'Attendance': Attendance,
        'ATTENDANCE_STATUS_CHOICES': ATTENDANCE_STATUS_CHOICES, # Optionally add the new list
        #'AttendanceStatus': AttendanceStatus, # ADDED/VERIFIED: Enum for attendance status
        'enrollments': enrollments # Association table
    }

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000))
    )
