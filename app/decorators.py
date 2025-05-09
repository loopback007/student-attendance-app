# app/decorators.py

from functools import wraps
from flask import flash, redirect, url_for, abort, request # Added request for redirect next
from flask_login import current_user
from app.models import UserRole # Assuming UserRole enum is in app.models

def role_required(role):
    """
    Generic decorator to require a specific role or higher (if roles have hierarchy).
    For this app, we'll check for specific roles.
    If a list of roles is provided, the user must have at least one of them.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                # This should ideally be handled by @login_required first,
                # but as a safeguard:
                flash("Please log in to access this page.", "info")
                return redirect(url_for('auth.login', next=request.path))
            
            # Ensure current_user.role is not None before accessing its value
            if current_user.role is None:
                flash("Your user role is not set. Please contact an administrator.", "danger")
                return abort(403) # Forbidden

            # Check if 'role' is a single UserRole enum member or a list/tuple of them
            if isinstance(role, (list, tuple)):
                if current_user.role not in role:
                    flash(f"You do not have the necessary permissions ({', '.join(r.name.title() for r in role)}) to access this page.", "warning")
                    return abort(403) # Forbidden
            else: # Single role
                if current_user.role != role:
                    flash(f"You must be a {role.name.title()} to access this page.", "warning")
                    return abort(403) # Forbidden
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Specific role decorators
def superuser_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login', next=request.path))
        if not hasattr(current_user, 'is_superuser') or not current_user.is_superuser: # Added hasattr check
            flash("This area is restricted to Superusers only.", "danger")
            return abort(403)
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """
    Decorator for routes that require ADMIN or SUPERUSER role.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            # Handled by @login_required, but good for direct use if needed
            return redirect(url_for('auth.login', next=request.path)) 
        # Check if user has ADMIN or SUPERUSER role
        if not (hasattr(current_user, 'role') and (current_user.role == UserRole.ADMIN or current_user.role == UserRole.SUPERUSER)):
            flash("You must be an Administrator to access this page.", "warning")
            return abort(403) # Forbidden
        return f(*args, **kwargs)
    return decorated_function

def teacher_required(f):
    """
    Decorator for routes that require TEACHER role.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login', next=request.path))
        if not (hasattr(current_user, 'role') and current_user.role == UserRole.TEACHER):
            flash("You must be a Teacher to access this page.", "warning")
            return abort(403) # Forbidden
        return f(*args, **kwargs)
    return decorated_function

def staff_required(f):
    """
    Decorator for routes that require STAFF, ADMIN, or SUPERUSER role.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login', next=request.path))
        if not (hasattr(current_user, 'role') and \
                (current_user.role == UserRole.STAFF or \
                 current_user.role == UserRole.ADMIN or \
                 current_user.role == UserRole.SUPERUSER)):
            flash("You must have Staff permissions (or higher) to access this page.", "warning")
            return abort(403) # Forbidden
        return f(*args, **kwargs)
    return decorated_function

