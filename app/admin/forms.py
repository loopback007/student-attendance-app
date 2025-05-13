# app/admin/forms.py
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, TextAreaField, PasswordField, BooleanField, SubmitField, DateField, SelectField, ValidationError, TimeField, HiddenField
from wtforms.validators import DataRequired, Length, Email, EqualTo, Optional, Regexp
from wtforms_sqlalchemy.fields import QuerySelectField, QuerySelectMultipleField 
from app.models import Subject, User, Student, UserRole, SubjectClass # Import UserRole
from wtforms.fields import FieldList, FormField # Ensure these are imported

# --- Helper functions ---
def get_all_subjects():
    return Subject.query.order_by(Subject.name)

def get_all_teachers():
    return User.query.filter_by(role=UserRole.TEACHER, is_active=True).order_by(User.last_name, User.first_name)

def get_students_not_in_class(class_id_for_form):
    if not class_id_for_form: 
        return Student.query.filter_by(is_active=True).order_by(Student.last_name, Student.first_name)
    current_class = SubjectClass.query.get(class_id_for_form)
    if not current_class: 
        return Student.query.filter_by(is_active=True).order_by(Student.last_name, Student.first_name)
    enrolled_student_ids = [student.id for student in current_class.students_enrolled]
    return Student.query.filter(Student.is_active==True, ~Student.id.in_(enrolled_student_ids)).order_by(Student.last_name, Student.first_name)

# --- Forms ---
class SubjectForm(FlaskForm):
    name = StringField('Subject Name', validators=[DataRequired(), Length(min=2, max=100)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=500)]) # Made Optional consistent with HolidayForm
    submit = SubmitField('Save Subject')

class TeacherForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=64)])
    email = StringField('Email Address', validators=[DataRequired(), Email(), Length(max=120)])
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=64)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=64)])
    password = PasswordField('Password', validators=[Optional(), Length(min=6, message="Password should be at least 6 characters long.")])
    confirm_password = PasswordField('Confirm Password', validators=[EqualTo('password', message='Passwords must match.')])
    is_active = BooleanField('User is active', default=True)
    submit = SubmitField('Save Teacher')
    
    user_id = None  # To store the ID of the user being edited

    def __init__(self, *args, **kwargs):
        super(TeacherForm, self).__init__(*args, **kwargs)
        editing_user = kwargs.get('obj') # Standard way to get object for pre-population
        if editing_user:
            self.user_id = editing_user.id
            # If editing and no new password is entered in the form submission, validators are not strictly needed for password
            # However, if a password IS entered, it should be validated.
            # This logic is better handled in the route or by making validators conditional based on data.
            # For simplicity, keep Length(min=6) but make DataRequired conditional in the route if password is not being changed.
            # Or, as done here, make password itself Optional. If provided, EqualTo for confirm_password will trigger.
        else: # For new user, password is required
            self.password.validators = [DataRequired(message="Password is required for new teachers."), Length(min=6, message="Password should be at least 6 characters long.")]
            self.confirm_password.validators = [DataRequired(message="Please confirm password."), EqualTo('password', message='Passwords must match.')]


    def validate_username(self, username_field):
        query = User.query.filter(User.username.ilike(username_field.data))
        if self.user_id: 
            query = query.filter(User.id != self.user_id)
        if query.first(): 
            raise ValidationError('This username is already taken.')

    def validate_email(self, email_field):
        query = User.query.filter(User.email.ilike(email_field.data))
        if self.user_id: 
            query = query.filter(User.id != self.user_id)
        if query.first(): 
            raise ValidationError('This email address is already registered.')

class StudentForm(FlaskForm):
    student_id_number = StringField('Student ID Number', validators=[DataRequired(), Length(min=1, max=50)])
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=64)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=64)])
    email = StringField('Email Address (Optional)', validators=[Optional(), Email(message="Invalid email format."), Length(max=120)])
    contact_number = StringField('Contact Number (Optional)', validators=[Optional(), Length(max=20)])
    date_of_birth = DateField('Date of Birth (YYYY-MM-DD, Optional)', format='%Y-%m-%d', validators=[Optional()])
    is_active = BooleanField('Student is currently active', default=True)
    is_in_arrears = BooleanField('Student account is in arrears', default=False)
    submit = SubmitField('Save Student')
    
    student_db_id = None # To store ID when editing

    def __init__(self, *args, **kwargs):
        super(StudentForm, self).__init__(*args, **kwargs)
        if 'obj' in kwargs and kwargs['obj']: 
            self.student_db_id = kwargs['obj'].id

    def validate_student_id_number(self, field):
        query = Student.query.filter(Student.student_id_number.ilike(field.data))
        if self.student_db_id: 
            query = query.filter(Student.id != self.student_db_id)
        if query.first(): 
            raise ValidationError('This Student ID Number is already in use.')

    def validate_email(self, field):
        if field.data: # Only validate if email is provided
            query = Student.query.filter(Student.email.ilike(field.data))
            if self.student_db_id: 
                query = query.filter(Student.id != self.student_db_id)
            if query.first(): 
                raise ValidationError('This email is already registered for another student.')

# --- Sub-Form for a single ClassSchedule entry ---
class ScheduleEntryForm(FlaskForm):
    """Sub-form for a single schedule entry (day, time, location)."""
    class Meta:
        csrf = False # Important for sub-forms in FieldList

    day_of_week = SelectField('Day', choices=[
        ("", "-- Select Day --"),
        ("Monday", "Monday"),
        ("Tuesday", "Tuesday"),
        ("Wednesday", "Wednesday"),
        ("Thursday", "Thursday"),
        ("Friday", "Friday"),
        ("Saturday", "Saturday"),
        ("Sunday", "Sunday")
    ], validators=[DataRequired(message="Please select a day.")])
    
    start_time = TimeField('Start Time', format='%H:%M', 
                           validators=[DataRequired(message="Please enter a start time.")])
    
    end_time = TimeField('End Time', format='%H:%M', 
                         validators=[DataRequired(message="Please enter an end time.")])
    
    location = StringField('Location', validators=[Optional(), Length(max=100)], render_kw={"placeholder": "e.g., Room 101"})
    schedule_id = HiddenField("Schedule ID") # For tracking existing schedules during edit

    def validate_end_time(self, field):
        if self.start_time.data and field.data:
            if field.data <= self.start_time.data:
                raise ValidationError('End time must be after start time.')
            # Consider adding datetime import if using datetime.combine here
            # from datetime import datetime, date as PyDate
            # start_dt = datetime.combine(PyDate.min, self.start_time.data)
            # end_dt = datetime.combine(PyDate.min, field.data)
            # if (end_dt - start_dt).total_seconds() < 15 * 60: # 15 minutes
            #     raise ValidationError('Minimum class duration is 15 minutes.')

# --- MODIFIED SubjectClassForm ---
class SubjectClassForm(FlaskForm):
    name = StringField('Class Name / Identifier', validators=[DataRequired(), Length(min=3, max=100)], description="E.g., 'Mathematics 10A'")
    subject = QuerySelectField('Subject', query_factory=get_all_subjects, get_label='name', allow_blank=False, validators=[DataRequired(message="Please select a subject.")])
    teacher = QuerySelectField('Teacher', query_factory=get_all_teachers, get_label=lambda user: f"{user.first_name} {user.last_name} ({user.username})", allow_blank=True, blank_text="-- Unassigned --", description="Assign a teacher (optional).", validators=[Optional()])
    
    # The old 'schedule_details' text field is now replaced by the structured 'schedules' FieldList.
    # Commented out, can be removed:
    # schedule_details = StringField('Schedule Details', validators=[Optional(), Length(max=200)], description="E.g., 'Mon 09:00-10:00 Room 101'")
    
    start_date = DateField('Overall Start Date (YYYY-MM-DD)', format='%Y-%m-%d', validators=[Optional()])
    end_date = DateField('Overall End Date (YYYY-MM-DD)', format='%Y-%m-%d', validators=[Optional()])
    academic_year = StringField('Academic Year', validators=[Optional(), Length(max=20)], description="E.g., '2024-2025'")
    
    # INTEGRATED: FieldList for managing ClassSchedule entries
    schedules = FieldList(FormField(ScheduleEntryForm), min_entries=1, label="Weekly Schedules") 
    # min_entries=1 ensures at least one schedule form is shown.
    # Use 0 if you want to rely on JavaScript to add the first entry.

    submit = SubmitField('Save Class')
    class_id = None # To store ID when editing, not a direct form field

    def __init__(self, *args, **kwargs):
        super(SubjectClassForm, self).__init__(*args, **kwargs)
        if 'obj' in kwargs and kwargs['obj']: 
            self.class_id = kwargs['obj'].id
            # Pre-populating FieldList (schedules) is usually done in the route function
            # before passing the form to the template, not in the form's __init__ itself.

    def validate_end_date(self, field):
        if field.data and self.start_date.data: 
            if field.data < self.start_date.data: 
                raise ValidationError('End date cannot be before the start date.')

class EnrollmentForm(FlaskForm):
    students_to_enroll = QuerySelectMultipleField('Select Students to Enroll', get_label=lambda student: f"{student.first_name} {student.last_name} ({student.student_id_number})", allow_blank=True, validators=[Optional()]) # Changed to Optional if no students are to be enrolled
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

class UserAdminForm(FlaskForm):
    username = StringField('Username', 
                           validators=[DataRequired(), Length(min=3, max=64)])
    email = StringField('Email Address', 
                        validators=[DataRequired(), Email(), Length(max=120)])
    first_name = StringField('First Name', 
                             validators=[Optional(), Length(max=64)])
    last_name = StringField('Last Name', 
                            validators=[Optional(), Length(max=64)])
    role = SelectField('Role', 
                       choices=[(role.value, role.name.title()) for role in UserRole], 
                       validators=[DataRequired(message="Please select a role for the user.")],
                       coerce=str) 
    password = PasswordField('Password', 
                             validators=[Optional(), Length(min=6, message="Password should be at least 6 characters long.")])
    confirm_password = PasswordField('Confirm Password', 
                                     validators=[EqualTo('password', message='Passwords must match.')])
    is_active = BooleanField('User is active', default=True)
    submit = SubmitField('Save User')
    user_id = None 
    def __init__(self, editing_user=None, *args, **kwargs):
        super(UserAdminForm, self).__init__(*args, **kwargs)
        self.editing_user = editing_user 
        if editing_user:
            self.user_id = editing_user.id
            if not self.password.data: 
                self.password.validators = [Optional(), Length(min=6, message="Password should be at least 6 characters long.")]
                self.confirm_password.validators = [Optional(), EqualTo('password', message='Passwords must match.')]
        else: 
            self.password.validators = [DataRequired(message="Password is required for new users."), Length(min=6, message="Password should be at least 6 characters long.")]
            self.confirm_password.validators = [DataRequired(message="Please confirm the password."), EqualTo('password', message='Passwords must match.')]

    def validate_username(self, username_field):
        query = User.query.filter(User.username.ilike(username_field.data))
        if self.user_id: 
            query = query.filter(User.id != self.user_id)
        user = query.first()
        if user:
            raise ValidationError('This username is already taken. Please choose a different one.')

    def validate_email(self, email_field):
        query = User.query.filter(User.email.ilike(email_field.data))
        if self.user_id: 
            query = query.filter(User.id != self.user_id)
        user = query.first()
        if user:
            raise ValidationError('This email address is already registered. Please choose a different one.')

    def validate_role(self, role_field):
        try:
            UserRole(role_field.data) 
        except ValueError:
            raise ValidationError("Invalid role selected.")

class HolidayForm(FlaskForm):
    name = StringField('Holiday Name',
                       validators=[DataRequired(message="Please enter the name of the holiday."),
                                   Length(min=3, max=100)])
    date = DateField('Date',
                     format='%Y-%m-%d', 
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
