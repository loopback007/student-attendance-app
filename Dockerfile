# Dockerfile

# Start with an official Python runtime as a parent image
FROM python:3.11-slim-buster

# Set the working directory in the container
WORKDIR /app

# Set environment variables
# Prevents Python from writing pyc files to disc (equivalent to python -B)
ENV PYTHONDONTWRITEBYTECODE 1
# Prevents Python from buffering stdout and stderr (important for logs)
ENV PYTHONUNBUFFERED 1
# Set Flask environment (can be overridden at runtime)
ENV FLASK_APP=run.py
ENV FLASK_ENV=production 
# Note: FLASK_ENV=production is the default in Flask 2.x if FLASK_DEBUG is not set.
# Gunicorn will be our production server, so FLASK_DEBUG should be 0.
ENV FLASK_DEBUG=0

# Install system dependencies (if any)
# For example, if you needed build tools for certain Python packages:
# RUN apt-get update && apt-get install -y --no-install-recommends gcc build-essential

# Install pipenv if you were using it (we are using requirements.txt)
# RUN pip install --upgrade pip
# RUN pip install pipenv

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container at /app
COPY . .

# Create a non-root user to run the application for better security
# RUN addgroup --system app && adduser --system --group app
# USER app
# For simplicity in this initial setup, we'll run as root. 
# Consider adding a non-root user for enhanced security in a production environment.

# Expose the port Gunicorn will run on (Gunicorn will bind to 0.0.0.0:5000 by default)
# This doesn't actually publish the port, docker-compose or docker run will do that.
EXPOSE 5000

# Define the command to run the application using Gunicorn
# Gunicorn is a WSGI HTTP server for UNIX.
# 'run:app' refers to the 'app' Flask application object created in 'run.py'.
# We bind to 0.0.0.0 so it's accessible from outside the container.
# Number of workers can be adjusted based on your server's CPU cores (typically 2-4 per core).
# `current_app.config.get('PORT', 5000)` in run.py is for flask dev server, gunicorn has its own port binding.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "run:app"]

# If you have an instance folder that needs to be created or have specific permissions:
# RUN mkdir -p instance && chown -R app:app instance
# VOLUME /app/instance 
# (If using a non-root user 'app', ensure this user owns the instance folder and any other necessary paths)
# For SQLite, the instance folder might contain the app.db if it's configured there.
# Our current config.py places app.db in the project root. If it were in 'instance/', 
# you'd want to ensure the 'instance' directory exists and is writable.
# Since our app.db is in the root of /app for now, it will be part of the main volume.
