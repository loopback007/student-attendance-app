# app/main/routes.py
from flask import render_template
from flask_login import login_required, current_user
from . import main # Import the blueprint instance

@main.route('/')
@main.route('/dashboard')
@login_required
def dashboard():
    """
    Main dashboard page.
    Renders the main dashboard template.
    """
    return render_template('main/dashboard.html', title='Dashboard')

