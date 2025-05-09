# app/auth/__init__.py

from flask import Blueprint

# Create a Blueprint instance for authentication routes
# 'auth' is the name of the blueprint
# __name__ helps Flask locate the blueprint's resources (like templates)
# template_folder='templates' specifies that this blueprint has its own templates subdirectory
auth = Blueprint('auth', __name__, template_folder='templates')

# Import routes and forms at the end to avoid circular dependencies
# These modules will use the 'auth' blueprint instance defined above
from . import routes #, forms (if you create a forms.py for WTForms)
