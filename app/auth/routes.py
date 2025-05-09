# app/auth/routes.py

from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from . import auth # Import the blueprint instance
from app.models import User # Import User model
from .forms import LoginForm # Import LoginForm
from app import db # To interact with the database
from urllib.parse import urlparse # MODIFIED: Replaced werkzeug.urls.url_parse

@auth.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handles user login.
    Authenticates users and logs them in if credentials are valid.
    """
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard')) # Redirect to the main dashboard

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        # Ensure user exists and password is correct
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password.', 'danger')
            return redirect(url_for('auth.login'))
        
        # Log the user in
        login_user(user, remember=form.remember_me.data)
        flash(f'Welcome back, {user.username}!', 'success')
        
        # Handle 'next' parameter for redirecting after login
        next_page = request.args.get('next')
        # Security check: ensure next_page is an internal path and not an external URL
        if not next_page or urlparse(next_page).netloc != '': 
            next_page = url_for('main.dashboard') # Default to dashboard if next_page is invalid or external
        return redirect(next_page)
    
    # For GET request, or if form validation fails, render the login template
    return render_template('auth/login.html', title='Sign In', form=form)

@auth.route('/logout')
@login_required # Ensure only logged-in users can logout
def logout():
    """
    Logs out the current user.
    """
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('auth.login')) # Redirect to login page after logout

# Placeholder for registration - we can implement this next if you like
# @auth.route('/register', methods=['GET', 'POST'])
# def register():
#     if current_user.is_authenticated:
#         return redirect(url_for('main.dashboard'))
#     # from .forms import RegistrationForm # Ensure this is imported if used
#     # form = RegistrationForm()
#     # if form.validate_on_submit():
#     #     user = User(username=form.username.data, email=form.email.data)
#     #     user.set_password(form.password.data)
#     #     # By default, new users could be 'STAFF' or require admin approval
#     #     # For now, let's assume a default role or handle it later
#     #     db.session.add(user)
#     #     db.session.commit()
#     #     flash('Congratulations, you are now a registered user!', 'success')
#     #     return redirect(url_for('auth.login'))
#     # return render_template('auth/register.html', title='Register', form=form)


# Example of a protected route (just for testing login_required)
# You can remove this or keep for testing purposes.
@auth.route('/protected_auth_route')
@login_required
def protected_auth_route():
    return f"This is a protected route within the AUTH blueprint. You are logged in as: {current_user.username}"
