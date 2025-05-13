# app/admin/forms.py
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, TextAreaField, PasswordField, BooleanField, SubmitField, DateField, SelectField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError, Optional
from wtforms_sqlalchemy.fields import QuerySelectField, QuerySelectMultipleField 
from app.models import Subject, User, Student, UserRole, SubjectClass # Import UserRole
from wtforms.fields import DateField

# --- Helper functions (get_all_subjects, get_all_teachers, get_students_not_in_class - Omitted for brevity) ---
def get_all_subjects():
    return Subject.query.order_by(Subject.name)
def get_all_teachers():
    return User.query.filter_by(role=UserRole.TEACHER).order_by(User.last_name, User.first_name)
def get_students_not_in_class(class_id_for_form):
    if not class_id_for_form: return Student.query.filter_by(is_active=True).order_by(Student.last_name, Student.first_name)
    current_class = SubjectClass.query.get(class_id_for_form)
    if not current_class: return Student.query.filter_by(is_active=True).order_by(Student.last_name, Student.first_name)
    enrolled_student_ids = [student.id for student in current_class.students_enrolled]
    return Student.query.filter(Student.is_active==True, ~Student.id.in_(enrolled_student_ids)).order_by(Student.last_name, Student.first_name)

# --- Existing Forms (SubjectForm, TeacherForm, StudentForm, SubjectClassForm, EnrollmentForm, StudentCSVImportForm, ClassCSVImportForm - Omitted for brevity) ---
class SubjectForm(FlaskForm):
    name = StringField('Subject Name', validators=[DataRequired(), Length(min=2, max=100)])
    description = TextAreaField('Description', validators=[Length(max=500)])
    submit = SubmitField('Save Subject')

class TeacherForm(FlaskForm): # This form is specifically for creating/editing Teachers by staff/admin
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=64)])
    email = StringField('Email Address', validators=[DataRequired(), Email(), Length(max=120)])
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=64)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=64)])
    password = PasswordField('Password', validators=[Length(min=6, message="Password should be at least 6 characters long.")])
    confirm_password = PasswordField('Confirm Password', validators=[EqualTo('password', message='Passwords must match.')])
    is_active = BooleanField('User is active', default=True)
    submit = SubmitField('Save Teacher')
    user_id = None 
    def __init__(self, *args, **kwargs):
        super(TeacherForm, self).__init__(*args, **kwargs)
        if 'obj' in kwargs and kwargs['obj']:
            self.user_id = kwargs['obj'].id
            if self.user_id:
                self.password.validators = [Length(min=6, message="Password should be at least 6 characters long.")] if self.password.data else []
                self.confirm_password.validators = [EqualTo('password', message='Passwords must match.')] if self.password.data else []
    def validate_username(self, username):
        query = User.query.filter(User.username.ilike(username.data))
        if self.user_id: query = query.filter(User.id != self.user_id)
        if query.first(): raise ValidationError('This username is already taken.')
    def validate_email(self, email):
        query = User.query.filter(User.email.ilike(email.data))
        if self.user_id: query = query.filter(User.id != self.user_id)
        if query.first(): raise ValidationError('This email address is already registered.')

class StudentForm(FlaskForm):
    student_id_number = StringField('Student ID Number', validators=[DataRequired(), Length(min=1, max=50)])
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=64)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=64)])
    email = StringField('Email Address (Optional)', validators=[Optional(), Email(), Length(max=120)])
    contact_number = StringField('Contact Number (Optional)', validators=[Optional(), Length(max=20)])
    date_of_birth = DateField('Date of Birth (YYYY-MM-DD, Optional)', format='%Y-%m-%d', validators=[Optional()])
    is_active = BooleanField('Student is currently active', default=True)
    is_in_arrears = BooleanField('Student account is in arrears', default=False)
    submit = SubmitField('Save Student')
    student_db_id = None
    def __init__(self, *args, **kwargs):
        super(StudentForm, self).__init__(*args, **kwargs)
        if 'obj' in kwargs and kwargs['obj']: self.student_db_id = kwargs['obj'].id
    def validate_student_id_number(self, field):
        query = Student.query.filter(Student.student_id_number.ilike(field.data))
        if self.student_db_id: query = query.filter(Student.id != self.student_db_id)
        if query.first(): raise ValidationError('This Student ID Number is already in use.')
    def validate_email(self, field):
        if field.data:
            query = Student.query.filter(Student.email.ilike(field.data))
            if self.student_db_id: query = query.filter(Student.id != self.student_db_id)
            if query.first(): raise ValidationError('This email is already registered for another student.')

class SubjectClassForm(FlaskForm):
    name = StringField('Class Name / Identifier', validators=[DataRequired(), Length(min=3, max=100)], description="E.g., 'Mathematics 10A'")
    subject = QuerySelectField('Subject', query_factory=get_all_subjects, get_label='name', allow_blank=False, validators=[DataRequired(message="Please select a subject.")])
    teacher = QuerySelectField('Teacher', query_factory=get_all_teachers, get_label=lambda user: f"{user.first_name} {user.last_name} ({user.username})", allow_blank=True, description="Assign a teacher (optional).")
    schedule_details = StringField('Schedule Details', validators=[Optional(), Length(max=200)], description="E.g., 'Mon 09:00-10:00 Room 101'")
    start_date = DateField('Start Date (YYYY-MM-DD)', format='%Y-%m-%d', validators=[Optional()])
    end_date = DateField('End Date (YYYY-MM-DD)', format='%Y-%m-%d', validators=[Optional()])
    academic_year = StringField('Academic Year', validators=[Optional(), Length(max=20)], description="E.g., '2024-2025'")
    submit = SubmitField('Save Class')
    class_id = None
    def __init__(self, *args, **kwargs):
        super(SubjectClassForm, self).__init__(*args, **kwargs)
        if 'obj' in kwargs and kwargs['obj']: self.class_id = kwargs['obj'].id
    def validate_end_date(self, field):
        if field.data and self.start_date.data:
            if field.data < self.start_date.data: raise ValidationError('End date cannot be before the start date.')

class EnrollmentForm(FlaskForm):
    students_to_enroll = QuerySelectMultipleField('Select Students to Enroll', get_label=lambda student: f"{student.first_name} {student.last_name} ({student.student_id_number})", allow_blank=True, validators=[DataRequired(message="Please select at least one student.")])
    submit = SubmitField('Enroll Selected Students')
    def __init__(self, class_id_for_form=None, *args, **kwargs):
        super(EnrollmentForm, self).__init__(*args, **kwargs)
        if class_id_for_form: self.students_to_enroll.query_factory = lambda: get_students_not_in_class(class_id_for_form)
        else: self.students_to_enroll.query_factory = lambda: Student.query.filter_by(is_active=True).order_by(Student.last_name, Student.first_name)

class StudentCSVImportForm(FlaskForm):
    csv_file = FileField('Student CSV File', validators=[FileRequired(message="Please select a CSV file to upload."), FileAllowed(['csv'], 'CSV files only!')])
    submit = SubmitField('Import Students from CSV')

class ClassCSVImportForm(FlaskForm):
    csv_file = FileField('Subject Class CSV File', validators=[FileRequired(message="Please select a CSV file to upload."), FileAllowed(['csv'], 'CSV files only!')])
    submit = SubmitField('Import Classes from CSV')

# --- New User Admin Form ---
class UserAdminForm(FlaskForm):
    """
    Form for Super Admins to create or edit any User.
    """
    username = StringField('Username', 
                           validators=[DataRequired(), Length(min=3, max=64)])
    email = StringField('Email Address', 
                        validators=[DataRequired(), Email(), Length(max=120)])
    first_name = StringField('First Name', 
                             validators=[Optional(), Length(max=64)]) # Optional for some system users
    last_name = StringField('Last Name', 
                            validators=[Optional(), Length(max=64)]) # Optional
    
    # Role selection using the UserRole enum
    role = SelectField('Role', 
                       choices=UserRole.get_choices(), # Uses the static method from UserRole enum
                       validators=[DataRequired(message="Please select a role for the user.")],
                       coerce=str) # Coerce to string as Enum values are strings

    password = PasswordField('Password', 
                             validators=[Length(min=6, message="Password should be at least 6 characters long.")])
    confirm_password = PasswordField('Confirm Password', 
                                     validators=[EqualTo('password', message='Passwords must match.')])
    
    is_active = BooleanField('User is active', default=True)
    submit = SubmitField('Save User')

    # Store the user ID for editing scenarios to check for unique username/email
    user_id = None 

    def __init__(self, editing_user=None, *args, **kwargs): # Changed obj to editing_user for clarity
        super(UserAdminForm, self).__init__(*args, **kwargs)
        self.editing_user = editing_user # Store the user being edited
        if editing_user:
            self.user_id = editing_user.id
            # Make password optional for editing unless new password is provided
            if self.user_id:
                self.password.validators = [Length(min=6, message="Password should be at least 6 characters long.")] if self.password.data else []
                self.confirm_password.validators = [EqualTo('password', message='Passwords must match.')] if self.password.data else []
        else: # For new user creation, password is required
            self.password.validators.insert(0, DataRequired(message="Password is required for new users."))
            self.confirm_password.validators.insert(0, DataRequired(message="Please confirm the password."))


    def validate_username(self, username_field):
        """Validate that the username is unique, or belongs to the current user being edited."""
        query = User.query.filter(User.username.ilike(username_field.data))
        if self.user_id: # If editing, exclude the current user from the check
            query = query.filter(User.id != self.user_id)
        user = query.first()
        if user:
            raise ValidationError('This username is already taken. Please choose a different one.')

    def validate_email(self, email_field):
        """Validate that the email is unique, or belongs to the current user being edited."""
        query = User.query.filter(User.email.ilike(email_field.data))
        if self.user_id: # If editing, exclude the current user from the check
            query = query.filter(User.id != self.user_id)
        user = query.first()
        if user:
            raise ValidationError('This email address is already registered. Please choose a different one.')

    def validate_role(self, role_field):
        """Ensure the selected role is a valid UserRole member."""
        try:
            UserRole(role_field.data) # Attempt to cast to the Enum
        except ValueError:
            raise ValidationError("Invalid role selected.")


# Add the new HolidayForm:
class HolidayForm(FlaskForm):
    name = StringField('Holiday Name',
                       validators=[DataRequired(message="Please enter the name of the holiday."),
                                   Length(min=3, max=100)])
    date = DateField('Date',
                     format='%Y-%m-%d', # Ensures date is processed correctly
                     validators=[DataRequired(message="Please select a date.")])
    type = SelectField('Type of Holiday/Event',
                       choices=[
                           ('Public Holiday', 'Public Holiday'),
                           ('School Holiday', 'School Holiday'),
                           ('School Event', 'School Event'),
                           ('Staff Day', 'Staff Day'),
                           ('Other', 'Other')
                       ],
                       validators=[DataRequired(message="Please select the type.")])
    description = TextAreaField('Description (Optional)',
                                validators=[Optional(), Length(max=500)])
    submit = SubmitField('Save Holiday')
