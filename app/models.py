# app/models.py

import enum
from datetime import datetime, date as PyDate # Use PyDate to avoid conflict with field name 'date'
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db, login_manager 

# --- Enums ---
class UserRole(enum.Enum):
    SUPERUSER = 'superuser'
    ADMIN = 'admin' 
    TEACHER = 'teacher'
    STAFF = 'staff'
    @staticmethod
    def get_choices():
        return [(choice.value, choice.name.title()) for choice in UserRole]

# Old AttendanceStatus enum (commented out as status field is now string-based)
# You might want to remove this definition if it's no longer used elsewhere.
# class AttendanceStatus(enum.Enum):
#     PRESENT = 'present'
#     ABSENT = 'absent'
#     LATE = 'late'
#     EXCUSED = 'excused'
#     @staticmethod
#     def get_choices():
#         return [(choice.value, choice.name.title()) for choice in AttendanceStatus]

# New list of choices for attendance forms
ATTENDANCE_STATUS_CHOICES = [
    ('present', 'Present'),
    ('absent', 'Absent'),
    ('late', 'Late'),
    ('excused', 'Excused'),
    ('public_holiday', 'Public Holiday'), # New status
    ('school_holiday', 'School Holiday'), # New status
]

# --- Association Table for Student and SubjectClass (Enrollment) ---
# This remains unchanged
enrollments = db.Table('enrollments',
    db.Column('student_id', db.Integer, db.ForeignKey('students.id'), primary_key=True),
    db.Column('class_id', db.Integer, db.ForeignKey('subject_classes.id'), primary_key=True),
    db.Column('enrollment_date', db.DateTime, default=datetime.utcnow)
)

# --- Models ---
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    email = db.Column(db.String(120), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    first_name = db.Column(db.String(64))
    last_name = db.Column(db.String(64))
    role = db.Column(db.Enum(UserRole), default=UserRole.STAFF, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    
    classes_taught = db.relationship('SubjectClass', backref='teacher_user', lazy='dynamic', foreign_keys='SubjectClass.teacher_user_id')
    # The 'recorded_attendances' relationship will be added by the backref from Attendance.recorded_by

    def __repr__(self):
        return f'<User {self.username} ({self.role.name})>'
    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    @property
    def is_superuser(self):
        return self.role == UserRole.SUPERUSER
    @property
    def is_admin(self):
        return self.role == UserRole.ADMIN or self.role == UserRole.SUPERUSER
    @property
    def is_teacher(self):
        return self.role == UserRole.TEACHER
    @property
    def is_staff(self):
        return self.role == UserRole.STAFF

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class Subject(db.Model):
    __tablename__ = 'subjects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    classes = db.relationship('SubjectClass', backref='subject_taught', lazy='dynamic')

    def __repr__(self):
        return f'<Subject {self.name}>'

class SubjectClass(db.Model):
    __tablename__ = 'subject_classes'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    teacher_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    schedule_details = db.Column(db.String(200), nullable=True)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    academic_year = db.Column(db.String(20), nullable=True)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    
    students_enrolled = db.relationship('Student', secondary=enrollments,
                                        backref=db.backref('classes_enrolled_in', lazy='dynamic'),
                                        lazy='dynamic')
    # The 'attendances' relationship will be added by the backref from Attendance.subject_class
    # Removed: attendance_records = db.relationship('Attendance', backref='attended_class', lazy='dynamic')
    
    def __repr__(self):
        teacher_name = self.teacher_user.username if self.teacher_user else "Unassigned"
        subject_name = self.subject_taught.name if self.subject_taught else "N/A"
        return f'<SubjectClass {self.name} ({subject_name} - Teacher: {teacher_name})>'

class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    student_id_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    first_name = db.Column(db.String(64), nullable=False)
    last_name = db.Column(db.String(64), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    contact_number = db.Column(db.String(20), nullable=True)
    date_of_birth = db.Column(db.Date, nullable=True)
    enrollment_date = db.Column(db.Date, default=lambda: PyDate.today()) # Adjusted to use PyDate
    is_active = db.Column(db.Boolean, default=True)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    is_in_arrears = db.Column(db.Boolean, default=False, nullable=False)

    # The 'attendances' relationship will be added by the backref from Attendance.student
    # Removed: attendance_entries = db.relationship('Attendance', backref='student_record', lazy='dynamic')

    def __repr__(self):
        return f'<Student {self.first_name} {self.last_name} ({self.student_id_number})>'
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

# --- Holiday Model (New) ---
class Holiday(db.Model):
    __tablename__ = 'holidays'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    date = db.Column(db.Date, nullable=False, unique=True) # Field name is 'date'
    type = db.Column(db.String(50), nullable=False)  # e.g., "Public Holiday", "School Holiday"
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Holiday {self.name} on {self.date} ({self.type})>"

# --- Attendance Model (Refactored) ---
class Attendance(db.Model):
    __tablename__ = 'attendance_records' # Table name remains 'attendance_records'
    id = db.Column(db.Integer, primary_key=True)

    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    subject_class_id = db.Column(db.Integer, db.ForeignKey('subject_classes.id'), nullable=False) # PREVIOUSLY: class_id
    date = db.Column(db.Date, nullable=False, default=lambda: PyDate.today()) # PREVIOUSLY: attendance_date. Field name is 'date'. Adjusted default.

    status = db.Column(db.String(50), nullable=False, default='absent') # Now a String
    remarks = db.Column(db.Text, nullable=True)
    recorded_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow) # PREVIOUSLY: recorded_at
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow) # New field
    session_time = db.Column(db.Time, nullable=True) # New field

    # Relationships
    student = db.relationship('Student', backref=db.backref('attendances', lazy='dynamic'))
    subject_class = db.relationship('SubjectClass', backref=db.backref('attendances', lazy='dynamic'))
    recorded_by = db.relationship('User', foreign_keys=[recorded_by_user_id], backref=db.backref('recorded_attendances', lazy='dynamic')) # PREVIOUSLY: recorder

    __table_args__ = (
        db.UniqueConstraint('student_id', 'subject_class_id', 'date', 'session_time', name='_student_class_date_session_uc'),
    )

    def __repr__(self):
        student_name = self.student.full_name if self.student else "N/A"
        class_name = self.subject_class.name if self.subject_class else "N/A"
        return f'<Attendance {student_name} - {class_name} on {self.date}: {self.status}>'
