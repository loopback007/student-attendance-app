# app/staff/__init__.py
from flask import Blueprint

staff = Blueprint('staff', __name__, template_folder='templates', url_prefix='/staff')

from . import routes
    
