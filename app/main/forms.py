# app/main/forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, ValidationError
from wtforms.validators import DataRequired, Length, Email, EqualTo, Optional
from flask_login import current_user
from app.models import User # Assuming your User model is in app.models

class UpdateProfileForm(FlaskForm):
    """Form for users to update their profile information."""
    username = StringField('Username', 
                           render_kw={'readonly': True}) # Username usually not changed by user
    email = StringField('Email', 
                        validators=[DataRequired(message="Email is required."), 
                                    Email(message="Invalid email address."), 
                                    Length(max=120)])
    first_name = StringField('First Name', 
                             validators=[Optional(), Length(max=64)])
    last_name = StringField('Last Name', 
                            validators=[Optional(), Length(max=64)])
    submit_profile = SubmitField('Update Profile')

    def validate_email(self, field):
        """Validate that the email is unique if it's changed."""
        if field.data.lower() != current_user.email.lower(): # Check if email has changed
            user = User.query.filter(User.email.ilike(field.data)).first()
            if user:
                raise ValidationError('That email address is already registered by another user. Please choose a different one.')

class ChangePasswordForm(FlaskForm):
    """Form for users to change their password."""
    current_password = PasswordField('Current Password', 
                                     validators=[DataRequired(message="Current password is required.")])
    new_password = PasswordField('New Password', 
                                 validators=[
                                     DataRequired(message="New password is required."),
                                     Length(min=6, message="New password must be at least 6 characters long.")
                                 ])
    confirm_new_password = PasswordField('Confirm New Password', 
                                         validators=[
                                             DataRequired(message="Please confirm your new password."),
                                             EqualTo('new_password', message='New passwords must match.')
                                         ])
    submit_password = SubmitField('Change Password')

    def validate_current_password(self, field):
        """Validate that the entered current password is correct."""
        if not current_user.check_password(field.data):
            raise ValidationError('Incorrect current password.')

