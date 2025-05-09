The Temple of Fine Arts Johor Bahru Attendance Tracker - Project Wiki
Last Updated: May 10, 2025
Table of Contents:
Introduction
Architecture
2.1 Backend
2.2 Frontend
2.3 Database
2.4 Web Server/Reverse Proxy
2.5 Containerization
2.6 Project Structure Overview
Core Features & Current Status
3.1 User Roles & Permissions
3.2 Data Management (CRUD Operations)
3.3 Attendance Tracking
3.4 Reporting & Dashboards
3.5 Data Import
3.6 Backup System
3.7 User Interface & Branding
Project Setup & Local Development
4.1 Prerequisites
4.2 Getting Started
Deployment Guide
5.1 Server Prerequisites
5.2 Deployment Steps
5.3 Managing the Deployment
5.4 Production Considerations
Key Configuration Files Overview
Future Enhancements / Roadmap
1. Introduction
The "The Temple of Fine Arts Johor Bahru Attendance Tracker" is a web-based application designed to streamline and manage student attendance for various classes and subjects. It provides role-based access for different user types, including administrators, staff, and teachers, each with specific functionalities.
Key Features:
User authentication and role management.
CRUD operations for subjects, classes, teachers, and students.
Student enrollment management for classes.
Teacher interface for marking daily/scheduled attendance.
Admin dashboard with key statistics.
Data import capabilities (CSV for students and classes).
Manual database backup functionality for administrators.
A modern, responsive user interface styled with Bootstrap 5 and custom branding.
2. Architecture
The application is built using a modern web stack, designed for modularity and scalability, and containerized for ease of deployment.
2.1 Backend
Flask (Python Web Framework): A lightweight and flexible microframework used for building the core application logic, routes, and APIs.
SQLAlchemy (ORM): Provides an Object-Relational Mapper, allowing interaction with the database using Python objects and abstracting SQL queries.
Gunicorn (WSGI Server): A production-ready Web Server Gateway Interface (WSGI) HTTP server used to run the Flask application in the Docker container.
2.2 Frontend
HTML5, CSS3, JavaScript: Standard web technologies for structuring, styling, and adding interactivity to the user interface.
Bootstrap 5: A popular CSS framework used for responsive design and pre-styled UI components, ensuring a consistent and modern look and feel. The application uses a custom primary theme color (#781013).
Jinja2 (Templating Engine): Integrated with Flask, Jinja2 is used to render dynamic HTML pages by embedding application data into templates.
2.3 Database
SQLite (Development/Default): Used as the default database for ease of setup and development. The database file (app.db) is persisted using Docker volumes in the containerized setup.
PostgreSQL (Production Recommendation): While currently using SQLite, PostgreSQL is recommended for a more robust and scalable production environment.
2.4 Web Server/Reverse Proxy
Nginx: A high-performance web server and reverse proxy. In this setup, Nginx sits in front of Gunicorn, handling incoming HTTP requests, and can be configured for tasks like SSL/TLS termination, serving static files directly (though currently proxied), load balancing, and caching.
2.5 Containerization
Docker: The application and its dependencies are packaged into a Docker image, ensuring consistency across different environments.
Docker Compose: Used to define and manage the multi-container application setup, including the Flask/Gunicorn application service and the Nginx service.
2.6 Project Structure Overview
student_attendance_app/
├── app/                        # Main Flask application package
│   ├── __init__.py             # App factory, blueprint registration
│   ├── admin/                  # Admin blueprint (routes, forms)
│   ├── auth/                   # Auth blueprint (routes, forms)
│   ├── main/                   # Main blueprint (general routes like dashboard)
│   ├── staff/                  # Staff blueprint (currently minimal, might merge with admin)
│   ├── teacher/                # Teacher blueprint (routes, forms)
│   ├── static/                 # Static files (CSS, JS, images - including custom icon)
│   ├── templates/              # HTML templates (Jinja2)
│   ├── models.py               # SQLAlchemy database models
│   ├── decorators.py           # Custom decorators (e.g., role_required)
│   └── ...                     # Other utility modules
├── migrations/                 # Flask-Migrate database migration scripts
├── instance/                   # Instance-specific files (e.g., db_backups/) - NOT version controlled
├── .env                        # Environment variables (local development, production secrets) - NOT version controlled
├── .gitignore                  # Specifies intentionally untracked files that Git should ignore
├── config.py                   # Configuration settings (database URI, secret key, etc.)
├── Dockerfile                  # Instructions to build the Flask application Docker image
├── docker-compose.yml          # Defines and orchestrates multi-container services (app, nginx)
├── nginx.conf                  # Nginx configuration file
├── requirements.txt            # Python dependencies
└── run.py                      # Script to run the Flask development server, Flask CLI commands


3. Core Features & Current Status
3.1 User Roles & Permissions
Implemented Roles:
SUPERUSER: Full access, can manage all aspects including other admins.
ADMIN: High-level access, can manage most data and users (except superusers).
TEACHER: Can view assigned classes, mark attendance, view class reports.
STAFF: Can manage subjects, classes, students, and teachers.
Default Admin Credentials: Set via config.py or environment variables (Username: admin, Password: adminpass by default).
Authentication: Flask-Login for session management.
Authorization: Role-based access control (RBAC) implemented using custom decorators (@admin_required, @teacher_required, @staff_required).
3.2 Data Management (CRUD Operations)
Subjects: Admins/Staff can Create, Read, Update, Delete subjects.
Teachers: Admins/Staff can Create, Read, Update, Delete teachers. Creating a teacher also creates an associated User account with the 'TEACHER' role.
Students: Admins/Staff can Create, Read, Update, Delete students. Includes an is_in_arrears flag.
Subject Classes: Admins/Staff can Create, Read, Update, Delete subject classes, assigning a subject, an optional teacher, and schedule details.
Student Enrollments: Admins/Staff can enroll students into subject classes and unenroll them.
3.3 Attendance Tracking
Marking Attendance: Teachers can access an interface to mark attendance (Present, Absent, Late, Excused) for each student in their assigned classes.
Date Handling:
The attendance page defaults to the correct day of the current week based on the class's fixed weekly schedule (parsed from schedule_details).
A date picker allows selecting other dates, with server-side validation to ensure it's a valid class day.
Remarks: Teachers can add optional remarks for each attendance entry.
Arrears Indicator: A visual flag (!) is shown next to a student's name on the attendance marking page if their account is marked as "in arrears".
3.4 Reporting & Dashboards
Admin Dashboard:
Displays key statistics: total active students, total teachers, total subjects, total classes.
Shows today's overall attendance rate.
Provides navigation links to management sections.
Teacher Dashboard ("My Classes"):
Lists classes assigned to the logged-in teacher.
Displays schedule details for each class.
Links to "Mark/View Attendance" and "View Report" for each class.
Class Attendance Report (Teacher View):
Provides a summary of attendance (Present, Absent, Late, Excused counts) for each student in a specific class.
Calculates a basic attendance percentage.
Shows the total number of unique class sessions for which attendance has been recorded.
3.5 Data Import
Import Students via CSV: Admins/Staff can upload a CSV file to bulk-create student records. Includes validation for required columns, unique student IDs/emails, and data type conversions.
Import Subject Classes via CSV: Admins/Staff can upload a CSV file to bulk-create subject classes, linking them to existing subjects and (optionally) teachers using identifiers.
3.6 Backup System
Manual Database Backup (SQLite): Admins can trigger the creation of a timestamped backup of the SQLite database file.
Backup Management: Admins can view a list of existing backup files and download them. Backups are stored in the instance/db_backups/ directory.
3.7 User Interface & Branding
Framework: Styled using Bootstrap 5 for a responsive and modern look.
Branding:
Title: "The Temple of Fine Arts Johor Bahru Attendance Tracker".
Icon: Custom icon used as a favicon and in the navbar.
Theme Color: Primary theme color set to #781013.
Refactoring: All primary admin list pages and form pages have been refactored to use Bootstrap 5 styling. Teacher-facing pages (my_classes.html, mark_attendance.html) have also been updated.
4. Project Setup & Local Development
4.1 Prerequisites
Python (version 3.9+ recommended, currently using 3.11 in Dockerfile)
pip (Python package installer)
A tool to create virtual environments (e.g., venv)
Git for version control
4.2 Getting Started
Clone the Repository:
git clone <repository_url>
cd student_attendance_app


Create and Activate Virtual Environment:
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate


Install Dependencies:
pip install -r requirements.txt


Set Up .env File:
Create a .env file in the project root.
Add essential environment variables:
SECRET_KEY=your_very_strong_random_secret_key_here
FLASK_CONFIG=development
# SQLALCHEMY_DATABASE_URI=sqlite:///app.db # Default, can be overridden
# DEFAULT_ADMIN_USERNAME=admin
# DEFAULT_ADMIN_PASSWORD=adminpass


Initialize Database:
Set the Flask app environment variable:
export FLASK_APP=run.py # On Windows: set FLASK_APP=run.py


Initialize the migration environment (only once per project):
flask db init


Create an initial migration script based on your models:
flask db migrate -m "Initial database schema"


Apply the migration to create database tables:
flask db upgrade


Create Initial Admin User:
flask create_admin
(Follow prompts or use default credentials if defined in config/env).
Run Development Server:
python run.py
The application should be accessible at http://localhost:5000 (or the port specified in run.py).
5. Deployment Guide
This guide outlines deploying the application to a new server environment using Docker and Docker Compose.
5.1 Server Prerequisites
Docker Engine: Latest stable version.
Docker Compose: Version 2.x or compatible.
Git: For cloning the application repository.
Firewall: Port 80 (for HTTP) and 443 (for HTTPS, if implemented) must be open to allow incoming web traffic.
5.2 Deployment Steps
Clone Repository:
git clone <your_repository_url>
cd student_attendance_app


Create .env File on Server:
In the project root (student_attendance_app/), create a .env file. This file should not be in version control.
Add production-specific environment variables:
# .env (on the server)
FLASK_APP=run.py
FLASK_CONFIG=production
FLASK_ENV=production
FLASK_DEBUG=0
DOCKER_CONTAINER=true
SECRET_KEY=a_very_strong_and_unique_production_secret_key
# Optional: Override default admin credentials for production
# DEFAULT_ADMIN_USERNAME=your_prod_admin_user
# DEFAULT_ADMIN_PASSWORD=your_strong_prod_admin_password
# If using an external database like PostgreSQL in production:
# DATABASE_URL=postgresql://user:password@host:port/dbname 


Build Docker Images:
Build the application service image:
sudo docker-compose build app
(Nginx uses a pre-built image from Docker Hub).
Start Services:
Run the application in detached mode:
sudo docker-compose up -d


Initial Database Setup (Inside Container):
Apply database migrations to the database within the Docker volume:
sudo docker-compose exec app flask db upgrade


Create the initial admin user (using credentials from the server's .env file or defaults):
sudo docker-compose exec app flask create_admin


Access Application:
Open a web browser and navigate to your server's IP address or configured domain name (e.g., http://your_server_ip).
5.3 Managing the Deployment
View Logs:
sudo docker-compose logs app
sudo docker-compose logs nginx
sudo docker-compose logs -f # Follow logs


Stop Services:
sudo docker-compose down
(To remove volumes as well, use sudo docker-compose down -v, but be cautious as this deletes data like the database if it's in a named volume not externally managed).
Restart Services:
sudo docker-compose restart app nginx


Update Application Code:
On the server, navigate to the project directory and pull the latest code: git pull
If requirements.txt or Dockerfile changed, rebuild the app image: sudo docker-compose build app
Restart the services to apply changes: sudo docker-compose up -d --no-deps app (or sudo docker-compose up -d to recreate all if needed).
5.4 Production Considerations
HTTPS/SSL: Crucial for production. Configure Nginx with SSL certificates (e.g., using Let's Encrypt).
Database: For production loads, migrate from SQLite to a more robust database like PostgreSQL (can also be containerized). Update DATABASE_URL accordingly.
Automated Backups: Implement regular, automated database backups stored securely (preferably off-site). The current manual backup is a starting point.
Nginx for Static Files: For optimal performance, configure Nginx to serve static files directly rather than proxying them through Gunicorn/Flask. This involves sharing the static volume or a "collectstatic" step.
Logging: Configure more robust and centralized logging for both the Flask app and Nginx.
Resource Monitoring & Scaling: Monitor server resources and adjust Gunicorn workers or server capacity as needed.
6. Key Configuration Files Overview
config.py: Contains Flask application configurations (secret keys, database URI, debug flags, default admin credentials). It uses different classes for development, testing, and production environments, selectable via the FLASK_CONFIG environment variable.
.env (Example): Used to store environment-specific variables, especially secrets, that are loaded by python-dotenv and Docker Compose. This file should not be committed to version control.
SECRET_KEY=your_secret_key_here
FLASK_CONFIG=development
DOCKER_CONTAINER=true # Set in docker-compose.yml for container-specific config
# DATABASE_URL=...


Dockerfile: Defines the steps to build the Docker image for the Flask application. It sets up the Python environment, copies application code, installs dependencies, and specifies the command to run Gunicorn.
docker-compose.yml: Orchestrates the multi-container application. It defines the app (Flask/Gunicorn) and nginx services, their build/image sources, environment variables, port mappings, and volumes (including app_db_data for persistent SQLite storage).
nginx.conf: The configuration file for the Nginx reverse proxy. It defines how Nginx listens for requests, proxies them to the Gunicorn server, and can be extended to handle static files, SSL, etc.
requirements.txt: Lists all Python dependencies for the project, installed using pip.
7. Future Enhancements / Roadmap (Potential)
Advanced Reporting:
Date range filtering for all reports.
Individual student attendance reports.
Export reports to CSV/PDF.
More detailed Admin Dashboard views (e.g., class-by-class attendance summaries).
SQL Database Import functionality.
User profile editing for all users.
Password reset functionality.
Two-Factor Authentication (2FA).
Automated email notifications (e.g., for low attendance).
Full Nginx static file serving optimization.
Comprehensive automated testing suite (unit and integration tests).
