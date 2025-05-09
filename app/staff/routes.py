# app/staff/routes.py
from flask import render_template
from flask_login import login_required
from . import staff
# from ..decorators import staff_required # We'll create this decorator later

@staff.route('/')
# @staff_required # Apply role protection later
@login_required # Basic login protection for now
def staff_dashboard():
    """
    Renders the staff dashboard template.
    """
    return render_template('staff/dashboard.html', title='Staff Dashboard')

