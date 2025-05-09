# app/teacher/__init__.py
from flask import Blueprint

teacher = Blueprint('teacher', __name__, template_folder='templates', url_prefix='/teacher')

from . import routes
    
