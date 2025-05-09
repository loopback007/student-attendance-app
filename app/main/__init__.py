# app/main/__init__.py
from flask import Blueprint

# Create a Blueprint instance for main application routes
# 'main' is the name of the blueprint
# __name__ helps Flask locate the blueprint's resources
# template_folder='templates' specifies a subdirectory for this blueprint's templates
main = Blueprint('main', __name__, template_folder='templates')

# Import routes at the end to avoid circular dependencies
# This module will use the 'main' blueprint instance defined above
from . import routes
