# app/admin/routes.py
from flask import render_template, request, redirect, url_for, flash, abort, current_app, send_from_directory
from flask_login import login_required, current_user
from wtforms.validators import DataRequired, Length, EqualTo 
from . import admin 
from app import db 
from app.decorators import staff_required, admin_required # Ensure admin_required is imported
from app.models import Subject, User, UserRole, Student, SubjectClass, Attendance, AttendanceStatus
from app.admin.forms import (
    SubjectForm, TeacherForm, StudentForm, SubjectClassForm, 
    EnrollmentForm, StudentCSVImportForm, ClassCSVImportForm,
    UserAdminForm # Import UserAdminForm
)
from datetime import date, datetime
import pandas as pd 
import io 
from werkzeug.utils import secure_filename
import os
import shutil

# Define a backup directory path.
BACKUP_DIR_NAME = 'db_backups'
def get_backup_dir():
    backup_path = os.path.join(current_app.instance_path, BACKUP_DIR_NAME)
    os.makedirs(backup_path, exist_ok=True)
    return backup_path

@admin.route('/')
@login_required
@staff_required 
def admin_dashboard():
    total_active_students = Student.query.filter_by(is_active=True).count()
    total_teachers = User.query.filter_by(role=UserRole.TEACHER, is_active=True).count()
    total_subjects = Subject.query.count()
    total_classes = SubjectClass.query.count()
    today = date.today()
    todays_attendance_records = Attendance.query.filter_by(attendance_date=today).all()
    present_or_late_today = 0
    total_records_today = len(todays_attendance_records)
    for record in todays_attendance_records:
        if record.status == AttendanceStatus.PRESENT or record.status == AttendanceStatus.LATE:
            present_or_late_today += 1
    todays_attendance_rate = 0
    if total_records_today > 0:
        todays_attendance_rate = (present_or_late_today / total_records_today) * 100
    stats = {
        'total_active_students': total_active_students, 'total_teachers': total_teachers,
        'total_subjects': total_subjects, 'total_classes': total_classes,
        'todays_attendance_present_late_count': present_or_late_today,
        'todays_attendance_total_records_count': total_records_today,
        'todays_attendance_rate': round(todays_attendance_rate, 2)
    }
    return render_template('admin/dashboard.html', title='Admin Dashboard', stats=stats)

# --- Existing CRUD Routes (Subjects, Teachers, Students, Classes, Enrollments, Imports, Backups - Omitted for brevity) ---
# ... (Keep all your existing routes here) ...
@admin.route('/subjects')
@login_required
@staff_required
def list_subjects():
    subjects = Subject.query.order_by(Subject.name.asc()).all()
    return render_template('admin/subjects.html', subjects=subjects, title="Manage Subjects")

@admin.route('/subjects/add', methods=['GET', 'POST'])
@login_required
@staff_required
def add_subject():
    form = SubjectForm()
    if form.validate_on_submit():
        existing_subject = Subject.query.filter(Subject.name.ilike(form.name.data)).first()
        if existing_subject:
            flash('A subject with this name already exists.', 'warning')
        else:
            subject = Subject(name=form.name.data, description=form.description.data)
            db.session.add(subject)
            db.session.commit()
            flash('Subject added successfully!', 'success')
            return redirect(url_for('admin.list_subjects'))
    return render_template('admin/subject_form.html', form=form, title="Add New Subject", legend="New Subject")

@admin.route('/subjects/edit/<int:subject_id>', methods=['GET', 'POST'])
@login_required
@staff_required
def edit_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    form = SubjectForm(obj=subject)
    if form.validate_on_submit():
        new_name = form.name.data
        conflicting_subject = Subject.query.filter(Subject.name.ilike(new_name), Subject.id != subject_id).first()
        if conflicting_subject:
            flash('Another subject with this name already exists.', 'warning')
        else:
            subject.name = new_name
            subject.description = form.description.data
            db.session.commit()
            flash('Subject updated successfully!', 'success')
            return redirect(url_for('admin.list_subjects'))
    return render_template('admin/subject_form.html', form=form, title="Edit Subject", legend=f"Edit Subject: {subject.name}", subject=subject)

@admin.route('/subjects/delete/<int:subject_id>', methods=['POST'])
@login_required
@staff_required
def delete_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    if subject.classes.first(): 
        flash('Cannot delete this subject as it is currently assigned to one or more classes. Please reassign or remove associated classes first.', 'danger')
        return redirect(url_for('admin.list_subjects'))
    try:
        db.session.delete(subject)
        db.session.commit()
        flash('Subject deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting subject: {str(e)}', 'danger')
    return redirect(url_for('admin.list_subjects'))

@admin.route('/teachers')
@login_required
@staff_required
def list_teachers():
    teachers = User.query.filter_by(role=UserRole.TEACHER).order_by(User.last_name, User.first_name).all()
    return render_template('admin/teachers.html', teachers=teachers, title="Manage Teachers")

@admin.route('/teachers/add', methods=['GET', 'POST'])
@login_required
@staff_required
def add_teacher():
    form = TeacherForm()
    form.password.validators = [DataRequired(), Length(min=6, message="Password should be at least 6 characters long.")]
    form.confirm_password.validators = [DataRequired(), EqualTo('password', message='Passwords must match.')]
    if form.validate_on_submit():
        new_teacher_user = User(
            username=form.username.data, email=form.email.data,
            first_name=form.first_name.data, last_name=form.last_name.data,
            role=UserRole.TEACHER, is_active=form.is_active.data
        )
        new_teacher_user.set_password(form.password.data)
        try:
            db.session.add(new_teacher_user)
            db.session.commit()
            flash(f'Teacher {new_teacher_user.first_name} {new_teacher_user.last_name} added successfully!', 'success')
            return redirect(url_for('admin.list_teachers'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding teacher: {str(e)}', 'danger')
    return render_template('admin/teacher_form.html', form=form, title="Add New Teacher", legend="New Teacher")

@admin.route('/teachers/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
@staff_required
def edit_teacher(user_id):
    teacher_user = User.query.filter_by(id=user_id, role=UserRole.TEACHER).first_or_404()
    form = TeacherForm(obj=teacher_user) 
    if request.method == 'POST' and not form.password.data:
        form.password.validators = []
        form.confirm_password.validators = []
    else: 
        form.password.validators = [Length(min=6, message="Password should be at least 6 characters long.")] if form.password.data or request.method == 'GET' else []
        form.confirm_password.validators = [EqualTo('password', message='Passwords must match.')] if form.password.data or request.method == 'GET' else []
    if form.validate_on_submit():
        teacher_user.username = form.username.data
        teacher_user.email = form.email.data
        teacher_user.first_name = form.first_name.data
        teacher_user.last_name = form.last_name.data
        teacher_user.is_active = form.is_active.data
        if form.password.data: 
            teacher_user.set_password(form.password.data)
        try:
            db.session.commit()
            flash(f'Teacher {teacher_user.first_name} {teacher_user.last_name} updated successfully!', 'success')
            return redirect(url_for('admin.list_teachers'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating teacher: {str(e)}', 'danger')
    return render_template('admin/teacher_form.html', form=form, title="Edit Teacher", 
                           legend=f"Edit Teacher: {teacher_user.first_name} {teacher_user.last_name}", 
                           teacher=teacher_user)

@admin.route('/teachers/delete/<int:user_id>', methods=['POST'])
@login_required
@staff_required
def delete_teacher(user_id):
    teacher_user = User.query.filter_by(id=user_id, role=UserRole.TEACHER).first_or_404()
    if teacher_user.classes_taught.first(): 
        flash(f'Cannot delete teacher {teacher_user.first_name} {teacher_user.last_name} as they are currently assigned to one or more classes. Please reassign classes first.', 'danger')
        return redirect(url_for('admin.list_teachers'))
    try:
        db.session.delete(teacher_user)
        db.session.commit()
        flash(f'Teacher {teacher_user.first_name} {teacher_user.last_name} deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting teacher: {str(e)}', 'danger')
    return redirect(url_for('admin.list_teachers'))

@admin.route('/students')
@login_required
@staff_required
def list_students():
    students = Student.query.order_by(Student.last_name, Student.first_name).all()
    return render_template('admin/students.html', students=students, title="Manage Students")

@admin.route('/students/add', methods=['GET', 'POST'])
@login_required
@staff_required
def add_student():
    form = StudentForm()
    if form.validate_on_submit():
        new_student = Student(
            student_id_number=form.student_id_number.data,
            first_name=form.first_name.data, last_name=form.last_name.data,
            email=form.email.data if form.email.data else None,
            contact_number=form.contact_number.data if form.contact_number.data else None,
            date_of_birth=form.date_of_birth.data,
            is_active=form.is_active.data,
            is_in_arrears=form.is_in_arrears.data 
        )
        try:
            db.session.add(new_student)
            db.session.commit()
            flash(f'Student {new_student.first_name} {new_student.last_name} added successfully!', 'success')
            return redirect(url_for('admin.list_students'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding student: {str(e)}', 'danger')
    return render_template('admin/student_form.html', form=form, title="Add New Student", legend="New Student")

@admin.route('/students/edit/<int:student_id>', methods=['GET', 'POST'])
@login_required
@staff_required
def edit_student(student_id):
    student = Student.query.get_or_404(student_id)
    form = StudentForm(obj=student)
    if form.validate_on_submit():
        student.student_id_number = form.student_id_number.data
        student.first_name = form.first_name.data
        student.last_name = form.last_name.data
        student.email = form.email.data if form.email.data else None
        student.contact_number = form.contact_number.data if form.contact_number.data else None
        student.date_of_birth = form.date_of_birth.data
        student.is_active = form.is_active.data
        student.is_in_arrears = form.is_in_arrears.data 
        try:
            db.session.commit()
            flash(f'Student {student.first_name} {student.last_name} updated successfully!', 'success')
            return redirect(url_for('admin.list_students'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating student: {str(e)}', 'danger')
    return render_template('admin/student_form.html', form=form, title="Edit Student", 
                           legend=f"Edit Student: {student.first_name} {student.last_name}", 
                           student=student)

@admin.route('/students/delete/<int:student_id>', methods=['POST'])
@login_required
@staff_required
def delete_student(student_id):
    student = Student.query.get_or_404(student_id)
    if student.attendance_entries.first() or student.classes_enrolled_in.first():
        flash(f'Cannot delete student {student.first_name} {student.last_name} as they have existing attendance records or class enrollments. Consider deactivating the student instead.', 'danger')
        return redirect(url_for('admin.list_students'))
    try:
        db.session.delete(student)
        db.session.commit()
        flash(f'Student {student.first_name} {student.last_name} deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting student: {str(e)}', 'danger')
    return redirect(url_for('admin.list_students'))

@admin.route('/classes')
@login_required
@staff_required
def list_subject_classes():
    classes = SubjectClass.query.options(
        db.joinedload(SubjectClass.subject_taught), 
        db.joinedload(SubjectClass.teacher_user)
    ).order_by(SubjectClass.name.asc()).all()
    return render_template('admin/subject_classes.html', classes=classes, title="Manage Subject Classes")

@admin.route('/classes/add', methods=['GET', 'POST'])
@login_required
@staff_required
def add_subject_class():
    form = SubjectClassForm()
    if form.validate_on_submit():
        new_class = SubjectClass(
            name=form.name.data, subject_id=form.subject.data.id,
            teacher_user_id=form.teacher.data.id if form.teacher.data else None,
            schedule_details=form.schedule_details.data, start_date=form.start_date.data,
            end_date=form.end_date.data, academic_year=form.academic_year.data
        )
        try:
            db.session.add(new_class)
            db.session.commit()
            flash(f'Class "{new_class.name}" added successfully!', 'success')
            return redirect(url_for('admin.list_subject_classes'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding class: {str(e)}', 'danger')
    return render_template('admin/subject_class_form.html', form=form, title="Add New Class", legend="New Subject Class")

@admin.route('/classes/edit/<int:class_id>', methods=['GET', 'POST'])
@login_required
@staff_required
def edit_subject_class(class_id):
    subject_class = SubjectClass.query.get_or_404(class_id)
    form = SubjectClassForm(obj=subject_class)
    if form.validate_on_submit():
        subject_class.name = form.name.data
        subject_class.subject_id = form.subject.data.id
        subject_class.teacher_user_id = form.teacher.data.id if form.teacher.data else None
        subject_class.schedule_details = form.schedule_details.data
        subject_class.start_date = form.start_date.data
        subject_class.end_date = form.end_date.data
        subject_class.academic_year = form.academic_year.data
        try:
            db.session.commit()
            flash(f'Class "{subject_class.name}" updated successfully!', 'success')
            return redirect(url_for('admin.list_subject_classes'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating class: {str(e)}', 'danger')
    return render_template('admin/subject_class_form.html', form=form, title="Edit Class",
                           legend=f"Edit Class: {subject_class.name}", subject_class=subject_class)

@admin.route('/classes/delete/<int:class_id>', methods=['POST'])
@login_required
@staff_required
def delete_subject_class(class_id):
    subject_class = SubjectClass.query.get_or_404(class_id)
    if subject_class.students_enrolled.first() or subject_class.attendance_records.first():
        flash(f'Cannot delete class "{subject_class.name}" as students are enrolled or attendance records exist. Please remove enrollments/records first.', 'danger')
        return redirect(url_for('admin.list_subject_classes'))
    try:
        db.session.delete(subject_class)
        db.session.commit()
        flash(f'Class "{subject_class.name}" deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting class: {str(e)}', 'danger')
    return redirect(url_for('admin.list_subject_classes'))

@admin.route('/classes/<int:class_id>/enrollments', methods=['GET', 'POST'])
@login_required
@staff_required
def manage_enrollments(class_id):
    current_class = SubjectClass.query.options(
        db.joinedload(SubjectClass.subject_taught),
        db.joinedload(SubjectClass.teacher_user)
    ).get_or_404(class_id)
    form = EnrollmentForm(class_id_for_form=class_id)
    if form.validate_on_submit():
        students_to_add = form.students_to_enroll.data 
        added_count = 0
        for student in students_to_add:
            if student not in current_class.students_enrolled:
                current_class.students_enrolled.append(student)
                added_count += 1
        if added_count > 0:
            try:
                db.session.commit()
                flash(f'{added_count} student(s) enrolled in "{current_class.name}" successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error enrolling students: {str(e)}', 'danger')
        else:
            flash('No new students were selected or all selected students are already enrolled.', 'info')
        return redirect(url_for('admin.manage_enrollments', class_id=class_id))
    enrolled_students = current_class.students_enrolled.order_by(Student.last_name, Student.first_name).all()
    return render_template('admin/manage_enrollments.html', 
                           form=form, current_class=current_class, 
                           enrolled_students=enrolled_students,
                           title=f"Manage Enrollments for {current_class.name}")

@admin.route('/classes/<int:class_id>/unenroll/<int:student_id>', methods=['POST'])
@login_required
@staff_required
def unenroll_student(class_id, student_id):
    current_class = SubjectClass.query.get_or_404(class_id)
    student_to_unenroll = Student.query.get_or_404(student_id)
    if student_to_unenroll in current_class.students_enrolled:
        current_class.students_enrolled.remove(student_to_unenroll)
        try:
            db.session.commit()
            flash(f'Student {student_to_unenroll.first_name} {student_to_unenroll.last_name} unenrolled from "{current_class.name}" successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error unenrolling student: {str(e)}', 'danger')
    else:
        flash('Student is not enrolled in this class.', 'info')
    return redirect(url_for('admin.manage_enrollments', class_id=class_id))

@admin.route('/students/import', methods=['GET', 'POST'])
@login_required
@staff_required
def import_students_csv():
    form = StudentCSVImportForm()
    if form.validate_on_submit():
        csv_file = form.csv_file.data
        try:
            csv_data = io.BytesIO(csv_file.read())
            df = pd.read_csv(csv_data)
            # ... (CSV processing logic as before) ...
            required_cols = {'student_id_number': 'student_id_number', 'first_name': 'first_name', 'last_name': 'last_name'}
            optional_cols = {'email': 'email', 'contact_number': 'contact_number', 'date_of_birth': 'date_of_birth', 'is_active': 'is_active', 'is_in_arrears': 'is_in_arrears'}
            df.columns = df.columns.str.lower().str.strip()
            missing_required = [col_display for col_key, col_display in required_cols.items() if col_key not in df.columns]
            if missing_required:
                flash(f"CSV file is missing required columns: {', '.join(missing_required)}. Please ensure your CSV has headers: student_id_number, first_name, last_name.", "danger")
                return render_template('admin/import_students_csv.html', form=form, title="Import Students from CSV")
            imported_count = 0; skipped_count = 0; error_rows = []
            for index, row in df.iterrows():
                try:
                    student_id_num = str(row[required_cols['student_id_number']]).strip(); first_name = str(row[required_cols['first_name']]).strip(); last_name = str(row[required_cols['last_name']]).strip()
                    if not student_id_num or not first_name or not last_name: skipped_count += 1; error_rows.append(f"Row {index+2}: Missing required field."); continue
                    if Student.query.filter_by(student_id_number=student_id_num).first(): skipped_count += 1; error_rows.append(f"Row {index+2}: Student ID '{student_id_num}' already exists."); continue
                    email = str(row.get(optional_cols['email'], '')).strip() if optional_cols['email'] in df.columns else None
                    if email == '': email = None
                    if email and Student.query.filter(Student.email.ilike(email)).first(): skipped_count += 1; error_rows.append(f"Row {index+2}: Email '{email}' already exists."); continue
                    contact_number = str(row.get(optional_cols['contact_number'], '')).strip() if optional_cols['contact_number'] in df.columns else None
                    if contact_number == '': contact_number = None
                    dob_str = str(row.get(optional_cols['date_of_birth'], '')).strip() if optional_cols['date_of_birth'] in df.columns else None; date_of_birth = None
                    if dob_str and dob_str.lower() not in ['nan', '']:
                        try: date_of_birth = datetime.strptime(dob_str, '%Y-%m-%d').date()
                        except ValueError:
                            try: date_of_birth = datetime.strptime(dob_str, '%d/%m/%Y').date()
                            except ValueError: skipped_count += 1; error_rows.append(f"Row {index+2}: Invalid date_of_birth format for '{dob_str}'."); continue
                    is_active_val = str(row.get(optional_cols['is_active'], 'True')).strip().lower(); is_active = is_active_val in ['true', '1', 'yes']
                    is_in_arrears_val = str(row.get(optional_cols['is_in_arrears'], 'False')).strip().lower(); is_in_arrears = is_in_arrears_val in ['true', '1', 'yes']
                    student = Student(student_id_number=student_id_num, first_name=first_name, last_name=last_name, email=email, contact_number=contact_number, date_of_birth=date_of_birth, is_active=is_active, is_in_arrears=is_in_arrears)
                    db.session.add(student); imported_count += 1
                except Exception as e_row: skipped_count += 1; error_rows.append(f"Row {index+2}: Error - {str(e_row)}")
            if imported_count > 0: db.session.commit()
            flash(f"Successfully imported {imported_count} students. Skipped {skipped_count} rows.", "success")
            if error_rows:
                flash("Errors encountered during import:", "warning");
                for err in error_rows[:10]: flash(err, "danger")
                if len(error_rows) > 10: flash(f"...and {len(error_rows) - 10} more errors not shown.", "warning")
            return redirect(url_for('admin.list_students'))
        except pd.errors.EmptyDataError: flash("The uploaded CSV file is empty.", "danger")
        except Exception as e: db.session.rollback(); flash(f"An error occurred during CSV processing: {str(e)}", "danger"); current_app.logger.error(f"CSV Import Error: {e}", exc_info=True)
    return render_template('admin/import_students_csv.html', form=form, title="Import Students from CSV")

@admin.route('/classes/import', methods=['GET', 'POST'])
@login_required
@staff_required
def import_classes_csv():
    form = ClassCSVImportForm()
    if form.validate_on_submit():
        csv_file = form.csv_file.data
        try:
            csv_data = io.BytesIO(csv_file.read())
            df = pd.read_csv(csv_data)
            # ... (CSV processing logic as before) ...
            required_cols = { 'class_name': 'class_name', 'subject_identifier': 'subject_identifier' }; optional_cols = { 'teacher_identifier': 'teacher_identifier', 'schedule_details': 'schedule_details', 'academic_year': 'academic_year', 'start_date': 'start_date', 'end_date': 'end_date' }
            df.columns = df.columns.str.lower().str.strip()
            missing_required = [col_display for col_key, col_display in required_cols.items() if col_key not in df.columns]
            if missing_required: flash(f"CSV file is missing required columns: {', '.join(missing_required)}.", "danger"); return render_template('admin/import_classes_csv.html', form=form, title="Import Subject Classes from CSV")
            imported_count = 0; skipped_count = 0; error_rows = []
            for index, row in df.iterrows():
                try:
                    class_name = str(row[required_cols['class_name']]).strip(); subject_identifier = str(row[required_cols['subject_identifier']]).strip()
                    if not class_name or not subject_identifier: skipped_count += 1; error_rows.append(f"Row {index+2}: Missing required field."); continue
                    subject = Subject.query.filter(Subject.name.ilike(subject_identifier)).first()
                    if not subject:
                        try: subject_id = int(subject_identifier); subject = Subject.query.get(subject_id)
                        except ValueError: subject = None
                    if not subject: skipped_count += 1; error_rows.append(f"Row {index+2}: Subject '{subject_identifier}' not found."); continue
                    teacher_user_id = None
                    if optional_cols['teacher_identifier'] in df.columns:
                        teacher_identifier = str(row.get(optional_cols['teacher_identifier'], '')).strip()
                        if teacher_identifier and teacher_identifier.lower() not in ['nan', '']:
                            teacher = User.query.filter((User.username.ilike(teacher_identifier) | User.email.ilike(teacher_identifier)) & (User.role == UserRole.TEACHER)).first()
                            if not teacher:
                                try: teacher_id_int = int(teacher_identifier); teacher = User.query.filter_by(id=teacher_id_int, role=UserRole.TEACHER).first()
                                except ValueError: teacher = None
                            if teacher: teacher_user_id = teacher.id
                            else: error_rows.append(f"Row {index+2}: Teacher '{teacher_identifier}' not found or not a Teacher. Class created without teacher.")
                    if SubjectClass.query.filter(SubjectClass.name.ilike(class_name)).first(): skipped_count += 1; error_rows.append(f"Row {index+2}: Class name '{class_name}' already exists."); continue
                    schedule_details = str(row.get(optional_cols['schedule_details'], '')).strip() if optional_cols['schedule_details'] in df.columns else None
                    academic_year = str(row.get(optional_cols['academic_year'], '')).strip() if optional_cols['academic_year'] in df.columns else None
                    start_date_str = str(row.get(optional_cols['start_date'], '')).strip() if optional_cols['start_date'] in df.columns else None; start_date = None
                    if start_date_str and start_date_str.lower() not in ['nan', '']:
                        try: start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                        except ValueError:
                            try: start_date = datetime.strptime(start_date_str, '%d/%m/%Y').date()
                            except ValueError: error_rows.append(f"Row {index+2}: Invalid start_date format for '{start_date_str}'.")
                    end_date_str = str(row.get(optional_cols['end_date'], '')).strip() if optional_cols['end_date'] in df.columns else None; end_date = None
                    if end_date_str and end_date_str.lower() not in ['nan', '']:
                        try: end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                        except ValueError:
                            try: end_date = datetime.strptime(end_date_str, '%d/%m/%Y').date()
                            except ValueError: error_rows.append(f"Row {index+2}: Invalid end_date format for '{end_date_str}'.")
                    if start_date and end_date and end_date < start_date: error_rows.append(f"Row {index+2}: End date ({end_date_str}) cannot be before start date ({start_date_str}). Dates ignored."); start_date, end_date = None, None
                    new_class = SubjectClass(name=class_name, subject_id=subject.id, teacher_user_id=teacher_user_id, schedule_details=schedule_details if schedule_details else None, academic_year=academic_year if academic_year else None, start_date=start_date, end_date=end_date)
                    db.session.add(new_class); imported_count += 1
                except Exception as e_row: skipped_count += 1; error_rows.append(f"Row {index+2}: Error processing row - {str(e_row)}")
            if imported_count > 0: db.session.commit()
            flash(f"Successfully imported {imported_count} classes. Skipped {skipped_count} rows.", "success")
            if error_rows:
                flash("Issues encountered during import (some rows might have been imported with partial data or skipped):", "warning");
                for err in error_rows[:10]: flash(err, "danger")
                if len(error_rows) > 10: flash(f"...and {len(error_rows) - 10} more issues not shown.", "warning")
            return redirect(url_for('admin.list_subject_classes'))
        except pd.errors.EmptyDataError: flash("The uploaded CSV file is empty.", "danger")
        except Exception as e: db.session.rollback(); flash(f"An error occurred during CSV processing: {str(e)}", "danger"); current_app.logger.error(f"Class CSV Import Error: {e}", exc_info=True)
    return render_template('admin/import_classes_csv.html', form=form, title="Import Subject Classes from CSV")

@admin.route('/backup', methods=['GET'])
@login_required
@admin_required 
def backup_management():
    backup_dir = get_backup_dir()
    try:
        backup_files = [f for f in os.listdir(backup_dir) if os.path.isfile(os.path.join(backup_dir, f))]
        backup_files.sort(reverse=True) 
    except FileNotFoundError: backup_files = []
    return render_template('admin/backup_management.html', backup_files=backup_files, title="Database Backup Management")

@admin.route('/backup/create', methods=['POST'])
@login_required
@admin_required
def create_backup():
    db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI')
    if not db_uri or not db_uri.startswith('sqlite:///'):
        flash("Backup currently only supported for SQLite databases.", "danger"); return redirect(url_for('admin.backup_management'))
    db_path_part = db_uri.split('sqlite:///', 1)[1]
    if os.name == 'nt' and db_path_part.startswith('/'): db_file_path = db_path_part[1:] if len(db_path_part) > 1 and db_path_part[2] == ':' else db_path_part
    else: db_file_path = os.path.join(current_app.root_path, '..', db_path_part) if not os.path.isabs(db_path_part) else db_path_part
    db_file_path = os.path.normpath(db_file_path)
    if not os.path.exists(db_file_path):
        flash(f"Database file not found: {db_file_path}", "danger"); return redirect(url_for('admin.backup_management'))
    backup_dir = get_backup_dir(); timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"attendance_app_backup_{timestamp}.db"; backup_filepath = os.path.join(backup_dir, backup_filename)
    try: shutil.copy2(db_file_path, backup_filepath); flash(f"Backup created: {backup_filename}", "success")
    except Exception as e: flash(f"Error creating backup: {str(e)}", "danger")
    return redirect(url_for('admin.backup_management'))

@admin.route('/backup/download/<filename>')
@login_required
@admin_required
def download_backup(filename):
    backup_dir = get_backup_dir()
    try: return send_from_directory(backup_dir, filename, as_attachment=True)
    except FileNotFoundError: abort(404)
    except Exception as e: flash(f"Error downloading backup: {str(e)}", "danger"); return redirect(url_for('admin.backup_management'))


# --- New User Management Routes (Admin Level) ---

@admin.route('/users')
@login_required
@admin_required # Only admins/superusers can manage all users
def list_all_users():
    """
    List all users in the system.
    """
    users = User.query.order_by(User.username).all()
    return render_template('admin/users.html', users=users, title="Manage All Users")

@admin.route('/users/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_user_admin():
    """
    Add a new user with any role (admin-level).
    """
    form = UserAdminForm() # Pass no 'editing_user' for new user
    if form.validate_on_submit():
        # Username and email uniqueness handled by form validators
        new_user = User(
            username=form.username.data,
            email=form.email.data,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            role=UserRole(form.role.data), # Convert string from form to UserRole enum
            is_active=form.is_active.data
        )
        new_user.set_password(form.password.data) # Password is required by form for new users
        
        try:
            db.session.add(new_user)
            db.session.commit()
            flash(f'User {new_user.username} ({new_user.role.name.title()}) created successfully!', 'success')
            return redirect(url_for('admin.list_all_users'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating user: {str(e)}', 'danger')
            current_app.logger.error(f"Error adding user by admin: {e}", exc_info=True)
            
    return render_template('admin/user_form_admin.html', form=form, title="Add New User", legend="Create New User")

@admin.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user_admin(user_id):
    """
    Edit any existing user's details, including role (admin-level).
    """
    user_to_edit = User.query.get_or_404(user_id)
    
    # Prevent admin from editing a superuser if current_user is not a superuser
    if user_to_edit.role == UserRole.SUPERUSER and not current_user.is_superuser:
        flash("Only Superusers can edit other Superusers.", "danger")
        return redirect(url_for('admin.list_all_users'))
        
    # Prevent admin from changing their own role to something less than admin, or deactivating themselves
    if user_to_edit.id == current_user.id and user_to_edit.role == UserRole.ADMIN:
        if UserRole(request.form.get('role')) != UserRole.ADMIN and UserRole(request.form.get('role')) != UserRole.SUPERUSER : # Check submitted role
             flash("Administrators cannot demote themselves from Admin/Superuser role.", "warning")
             # Potentially redirect or re-render form with error, here just flashing
        if not request.form.get('is_active', type=lambda v: v.lower() == 'true' or v == 'y'): # Check submitted active status
            flash("Administrators cannot deactivate their own account.", "warning")


    form = UserAdminForm(editing_user=user_to_edit, obj=user_to_edit) # Pass user for pre-population and validation context

    if form.validate_on_submit():
        user_to_edit.username = form.username.data
        user_to_edit.email = form.email.data
        user_to_edit.first_name = form.first_name.data
        user_to_edit.last_name = form.last_name.data
        
        # Handle role change carefully
        new_role = UserRole(form.role.data)
        if user_to_edit.id == current_user.id and current_user.role == UserRole.ADMIN and new_role not in [UserRole.ADMIN, UserRole.SUPERUSER]:
            flash("As an Administrator, you cannot change your own role to be less privileged than Admin.", "danger")
        elif user_to_edit.role == UserRole.SUPERUSER and not current_user.is_superuser:
            # This case should be caught above, but as a double check for role field
            flash("Only Superusers can change the role of a Superuser.", "danger")
        else:
            user_to_edit.role = new_role
            
        user_to_edit.is_active = form.is_active.data
        if user_to_edit.id == current_user.id and not form.is_active.data:
            flash("You cannot deactivate your own account.", "danger")
            user_to_edit.is_active = True # Revert

        if form.password.data: # If a new password was entered
            user_to_edit.set_password(form.password.data)
            
        try:
            db.session.commit()
            flash(f'User {user_to_edit.username} updated successfully!', 'success')
            return redirect(url_for('admin.list_all_users'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating user: {str(e)}', 'danger')
            current_app.logger.error(f"Error editing user by admin: {e}", exc_info=True)
    
    # For GET request, pre-populate form fields (obj=user_to_edit handles this)
    # Ensure the role is correctly set for the form's SelectField
    if request.method == 'GET':
        form.role.data = user_to_edit.role.value

    return render_template('admin/user_form_admin.html', form=form, title="Edit User", 
                           legend=f"Edit User: {user_to_edit.username}", user_being_edited=user_to_edit)


@admin.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user_admin(user_id):
    """
    Deletes or deactivates a user (admin-level).
    """
    user_to_delete = User.query.get_or_404(user_id)

    if user_to_delete.id == current_user.id:
        flash("You cannot delete your own account.", "danger")
        return redirect(url_for('admin.list_all_users'))

    if user_to_delete.role == UserRole.SUPERUSER and not current_user.is_superuser:
        flash("Only Superusers can delete other Superusers.", "danger")
        return redirect(url_for('admin.list_all_users'))
    
    # Add more checks here if needed, e.g., if a teacher is assigned to classes.
    if user_to_delete.role == UserRole.TEACHER and user_to_delete.classes_taught.first():
        flash(f"Cannot delete teacher {user_to_delete.username} as they are assigned to classes. Please reassign classes first or deactivate the user.", "warning")
        return redirect(url_for('admin.list_all_users'))

    try:
        # Option 1: Deactivate instead of delete
        # user_to_delete.is_active = False
        # db.session.commit()
        # flash(f'User {user_to_delete.username} has been deactivated.', 'success')
        
        # Option 2: Actual Deletion (use with caution)
        db.session.delete(user_to_delete)
        db.session.commit()
        flash(f'User {user_to_delete.username} has been deleted.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error processing user account: {str(e)}', 'danger')
        current_app.logger.error(f"Error deleting/deactivating user by admin: {e}", exc_info=True)
        
    return redirect(url_for('admin.list_all_users'))

