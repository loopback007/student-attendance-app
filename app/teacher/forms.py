# app/teacher/forms.py
from flask_wtf import FlaskForm
from wtforms import DateField, SelectField, StringField, SubmitField, HiddenField
from wtforms.fields import FieldList, FormField # For repeating sub-forms
from wtforms.validators import DataRequired, Optional, Length # IMPORTED Length
#from app.models import AttendanceStatus # Enum for attendance choices
from app.models import ATTENDANCE_STATUS_CHOICES # IMPORT THIS
from datetime import date

class StudentAttendanceEntryForm(FlaskForm):
    """
    Sub-form for a single student's attendance entry.
    This will be used within a FieldList in the main attendance form.
    """
    student_id = HiddenField('Student ID', validators=[DataRequired()])
    # student_name field is for display only in the template, not a real form field to submit
    status = SelectField('Status', 
                         choices=ATTENDANCE_STATUS_CHOICES, # USE THE NEW LIST
                         validators=[DataRequired(message="Please select a status.")],
                         coerce=str) # Coerce to string as Enum values are strings
    remarks = StringField('Remarks', validators=[Optional(), Length(max=200)]) # Length validator used here

    # WTForms needs a way to instantiate this without CSRF for FieldList
    class Meta:
        csrf = False


class MarkAttendanceForm(FlaskForm):
    """
    Main form for a teacher to mark attendance for a class on a specific date.
    """
    attendance_date = DateField('Attendance Date', 
                                format='%Y-%m-%d', 
                                validators=[DataRequired()],
                                default=date.today) # Default to today's date
    
    # This FieldList will hold one StudentAttendanceEntryForm for each student
    students_attendance = FieldList(FormField(StudentAttendanceEntryForm))
    
    submit = SubmitField('Save Attendance')

