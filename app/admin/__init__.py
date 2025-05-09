# app/admin/__init__.py
from flask import Blueprint

# Removed template_folder so it uses the app's global template folder (app/templates/)
# The path 'admin/dashboard.html' in render_template will then correctly point to
# app/templates/admin/dashboard.html
admin = Blueprint('admin', __name__, url_prefix='/admin')

from . import routes # Import routes after blueprint creation
