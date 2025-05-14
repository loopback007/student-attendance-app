# app/admin/routes.py
from flask import render_template, request, redirect, url_for, flash, abort, current_app, send_from_directory
from flask_login import login_required, current_user
from wtforms.validators import DataRequired, Length, EqualTo 
from . import admin # Blueprint
from app import db 
from app.decorators import staff_required, admin_required 
from app.models import Subject, User, UserRole, Student, SubjectClass, Attendance, Holiday, ClassSchedule 
from app.admin.forms import (
    SubjectForm, TeacherForm, StudentForm, SubjectClassForm, 
    EnrollmentForm, StudentCSVImportForm, ClassCSVImportForm,
    UserAdminForm, HolidayForm 
)
from datetime import date, datetime, time 
import pandas as pd 
import io 
from werkzeug.utils import secure_filename 
import os
import shutil
from sqlalchemy import text # <<< ADD THIS IMPORT

# --- Backup Directory ---
BACKUP_DIR_NAME = 'db_backups'
def get_backup_dir():
    backup_path = os.path.join(current_app.instance_path, BACKUP_DIR_NAME)
    os.makedirs(backup_path, exist_ok=True)
    return backup_path

# --- Admin Dashboard ---
@admin.route('/')
@login_required
@staff_required 
def admin_dashboard():
    total_active_students = Student.query.filter_by(is_active=True).count()
    total_teachers = User.query.filter_by(role=UserRole.TEACHER, is_active=True).count()
    total_subjects = Subject.query.count()
    total_classes = SubjectClass.query.count()
    today = date.today() 
    todays_attendance_records = Attendance.query.filter_by(date=today).all()
    present_or_late_today = 0
    total_records_today = len(todays_attendance_records)
    for record in todays_attendance_records:
        if record.status == 'present' or record.status == 'late':
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

# --- Subject CRUD Routes ---
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
        current_app.logger.error(f"Error deleting subject {subject_id}: {e}", exc_info=True)
    return redirect(url_for('admin.list_subjects'))

# --- Teacher CRUD Routes ---
# ... (Teacher routes remain the same) ...
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
            current_app.logger.error(f"Error adding teacher: {e}", exc_info=True)
    return render_template('admin/teacher_form.html', form=form, title="Add New Teacher", legend="New Teacher")

@admin.route('/teachers/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
@staff_required
def edit_teacher(user_id):
    teacher_user = User.query.filter_by(id=user_id, role=UserRole.TEACHER).first_or_404()
    form = TeacherForm(obj=teacher_user) 
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
            current_app.logger.error(f"Error updating teacher {user_id}: {e}", exc_info=True)
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
        current_app.logger.error(f"Error deleting teacher {user_id}: {e}", exc_info=True)
    return redirect(url_for('admin.list_teachers'))

# --- Student CRUD Routes ---
# ... (Student routes remain the same) ...
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
            current_app.logger.error(f"Error adding student: {e}", exc_info=True)
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
            current_app.logger.error(f"Error updating student {student_id}: {e}", exc_info=True)
    return render_template('admin/student_form.html', form=form, title="Edit Student", 
                           legend=f"Edit Student: {student.first_name} {student.last_name}", 
                           student=student)

@admin.route('/students/delete/<int:student_id>', methods=['POST'])
@login_required
@staff_required
def delete_student(student_id):
    student = Student.query.get_or_404(student_id)
    if student.attendances.first() or student.classes_enrolled_in.first():
        flash(f'Cannot delete student {student.first_name} {student.last_name} as they have existing attendance records or class enrollments. Consider deactivating the student instead.', 'danger')
        return redirect(url_for('admin.list_students'))
    try:
        db.session.delete(student)
        db.session.commit()
        flash(f'Student {student.first_name} {student.last_name} deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting student: {str(e)}', 'danger')
        current_app.logger.error(f"Error deleting student {student_id}: {e}", exc_info=True)
    return redirect(url_for('admin.list_students'))


# --- SubjectClass (Classes) CRUD Routes ---
@admin.route('/classes')
@login_required
@staff_required
def list_subject_classes():
    classes = SubjectClass.query.options(
        db.joinedload(SubjectClass.subject_taught), 
        db.joinedload(SubjectClass.teacher_user)
    ).order_by(SubjectClass.name.asc()).all()
    # MODIFIED: Pass 'sa_text=text' to the template for sorting schedules
    return render_template('admin/subject_classes.html', classes=classes, title="Manage Subject Classes", sa_text=text)

@admin.route('/classes/add', methods=['GET', 'POST'])
@login_required
@staff_required
def add_subject_class():
    form = SubjectClassForm()
    if form.validate_on_submit():
        new_class = SubjectClass(
            name=form.name.data, 
            subject_id=form.subject.data.id,
            teacher_user_id=form.teacher.data.id if form.teacher.data else None,
            start_date=form.start_date.data,
            end_date=form.end_date.data, 
            academic_year=form.academic_year.data
        )
        db.session.add(new_class) 
        
        for schedule_entry_form_data in form.schedules.data:
            if schedule_entry_form_data['day_of_week'] and \
               schedule_entry_form_data['start_time'] and \
               schedule_entry_form_data['end_time']:
                
                new_schedule = ClassSchedule(
                    subject_class=new_class, 
                    day_of_week=schedule_entry_form_data['day_of_week'],
                    start_time=schedule_entry_form_data['start_time'],
                    end_time=schedule_entry_form_data['end_time'],
                    location=schedule_entry_form_data.get('location')
                )
                db.session.add(new_schedule) 
        
        try:
            db.session.commit() 
            flash(f'Class "{new_class.name}" and its schedules added successfully!', 'success')
            return redirect(url_for('admin.list_subject_classes'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding class: {str(e)}', 'danger')
            current_app.logger.error(f"Error adding class: {e}", exc_info=True)
            
    if request.method == 'GET' and not form.schedules.entries and form.schedules.min_entries > 0:
        for _ in range(form.schedules.min_entries):
            form.schedules.append_entry()
            
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
        subject_class.start_date = form.start_date.data
        subject_class.end_date = form.end_date.data
        subject_class.academic_year = form.academic_year.data
        
        existing_schedule_ids = {schedule.id for schedule in subject_class.schedules}
        submitted_schedule_ids = set()
        new_schedules_to_add = []

        for schedule_form_data in form.schedules.data:
            schedule_id_str = schedule_form_data.get('schedule_id')
            schedule_id = int(schedule_id_str) if schedule_id_str and schedule_id_str.isdigit() else None

            if schedule_form_data['day_of_week'] and schedule_form_data['start_time'] and schedule_form_data['end_time']:
                if schedule_id and schedule_id in existing_schedule_ids:
                    sched_to_update = ClassSchedule.query.get(schedule_id)
                    if sched_to_update:
                        sched_to_update.day_of_week = schedule_form_data['day_of_week']
                        sched_to_update.start_time = schedule_form_data['start_time']
                        sched_to_update.end_time = schedule_form_data['end_time']
                        sched_to_update.location = schedule_form_data.get('location')
                        db.session.add(sched_to_update)
                    submitted_schedule_ids.add(schedule_id)
                else:
                    new_schedule = ClassSchedule(
                        subject_class_id=subject_class.id,
                        day_of_week=schedule_form_data['day_of_week'],
                        start_time=schedule_form_data['start_time'],
                        end_time=schedule_form_data['end_time'],
                        location=schedule_form_data.get('location')
                    )
                    new_schedules_to_add.append(new_schedule)
        
        for ns in new_schedules_to_add:
            db.session.add(ns)

        ids_to_delete = existing_schedule_ids - submitted_schedule_ids
        for id_to_del in ids_to_delete:
            sched_to_delete = ClassSchedule.query.get(id_to_del)
            if sched_to_delete:
                db.session.delete(sched_to_delete)
        
        try:
            db.session.commit()
            flash(f'Class "{subject_class.name}" and its schedules updated successfully!', 'success')
            return redirect(url_for('admin.list_subject_classes'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating class: {str(e)}', 'danger')
            current_app.logger.error(f"Error updating class {class_id}: {e}", exc_info=True)
    
    if request.method == 'GET':
        while len(form.schedules.entries) > 0:
            form.schedules.pop_entry()
        if subject_class.schedules:
            for schedule in subject_class.schedules.order_by(ClassSchedule.day_of_week, ClassSchedule.start_time).all(): # Simple sort for pre-population
                form.schedules.append_entry({
                    'schedule_id': schedule.id,
                    'day_of_week': schedule.day_of_week,
                    'start_time': schedule.start_time,
                    'end_time': schedule.end_time,
                    'location': schedule.location
                })
        if not form.schedules.entries and form.schedules.min_entries > 0:
            for _ in range(form.schedules.min_entries):
                form.schedules.append_entry()

    return render_template('admin/subject_class_form.html', form=form, title="Edit Class",
                           legend=f"Edit Class: {subject_class.name}", subject_class=subject_class)

@admin.route('/classes/delete/<int:class_id>', methods=['POST'])
@login_required
@staff_required
def delete_subject_class(class_id):
    subject_class = SubjectClass.query.get_or_404(class_id)
    if subject_class.students_enrolled.first() or subject_class.attendances.first():
        flash(f'Cannot delete class "{subject_class.name}" as students are enrolled or attendance records exist. Please remove enrollments/records first.', 'danger')
        return redirect(url_for('admin.list_subject_classes'))
    try:
        db.session.delete(subject_class) 
        db.session.commit()
        flash(f'Class "{subject_class.name}" deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting class: {str(e)}', 'danger')
        current_app.logger.error(f"Error deleting class {class_id}: {e}", exc_info=True)
    return redirect(url_for('admin.list_subject_classes'))

# --- Enrollment Routes ---
# ... (Enrollment routes remain the same) ...
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
                current_app.logger.error(f"Error enrolling students for class {class_id}: {e}", exc_info=True)
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
            current_app.logger.error(f"Error unenrolling student {student_id} from class {class_id}: {e}", exc_info=True)
    else:
        flash('Student is not enrolled in this class.', 'info')
    return redirect(url_for('admin.manage_enrollments', class_id=class_id))

# --- CSV Import Routes ---
# ... (CSV Import routes remain the same) ...
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
            required_cols = {'student_id_number': 'student_id_number', 'first_name': 'first_name', 'last_name': 'last_name'}
            optional_cols = {'email': 'email', 'contact_number': 'contact_number', 'date_of_birth': 'date_of_birth', 'is_active': 'is_active', 'is_in_arrears': 'is_in_arrears'}
            df.columns = df.columns.str.lower().str.strip()
            missing_required = [col_display for col_key, col_display in required_cols.items() if col_key not in df.columns]
            if missing_required:
                flash(f"CSV file is missing required columns: {', '.join(missing_required)}. Please ensure your CSV has headers: student_id_number, first_name, last_name.", "danger")
                return render_template('admin/import_students_csv.html', form=form, title="Import Students from CSV")
            
            imported_count = 0; skipped_count = 0; error_rows = []
            for index, row_data in df.iterrows():
                row_series = pd.Series(row_data)
                try:
                    student_id_num = str(row_series[required_cols['student_id_number']]).strip(); first_name = str(row_series[required_cols['first_name']]).strip(); last_name = str(row_series[required_cols['last_name']]).strip()
                    if not student_id_num or not first_name or not last_name: skipped_count += 1; error_rows.append(f"Row {index+2}: Missing required field."); continue
                    if Student.query.filter_by(student_id_number=student_id_num).first(): skipped_count += 1; error_rows.append(f"Row {index+2}: Student ID '{student_id_num}' already exists."); continue
                    
                    email_val = str(row_series.get(optional_cols['email'], '')).strip() if optional_cols['email'] in row_series else None
                    email = email_val if email_val and email_val.lower() != 'nan' else None
                    if email and Student.query.filter(Student.email.ilike(email)).first(): skipped_count += 1; error_rows.append(f"Row {index+2}: Email '{email}' already exists."); continue
                    
                    contact_val = str(row_series.get(optional_cols['contact_number'], '')).strip() if optional_cols['contact_number'] in row_series else None
                    contact_number = contact_val if contact_val and contact_val.lower() != 'nan' else None

                    dob_str = str(row_series.get(optional_cols['date_of_birth'], '')).strip() if optional_cols['date_of_birth'] in row_series else None; date_of_birth = None
                    if dob_str and dob_str.lower() not in ['nan', '']:
                        try: date_of_birth = datetime.strptime(dob_str, '%Y-%m-%d').date()
                        except ValueError:
                            try: date_of_birth = datetime.strptime(dob_str, '%d/%m/%Y').date()
                            except ValueError: skipped_count += 1; error_rows.append(f"Row {index+2}: Invalid date_of_birth format for '{dob_str}'. Use YYYY-MM-DD or DD/MM/YYYY."); continue
                    
                    is_active_val = str(row_series.get(optional_cols['is_active'], 'True')).strip().lower(); is_active = is_active_val in ['true', '1', 'yes', 't']
                    is_in_arrears_val = str(row_series.get(optional_cols['is_in_arrears'], 'False')).strip().lower(); is_in_arrears = is_in_arrears_val in ['true', '1', 'yes', 't']
                    
                    student = Student(student_id_number=student_id_num, first_name=first_name, last_name=last_name, email=email, contact_number=contact_number, date_of_birth=date_of_birth, is_active=is_active, is_in_arrears=is_in_arrears)
                    db.session.add(student); imported_count += 1
                except Exception as e_row: skipped_count += 1; error_rows.append(f"Row {index+2}: Error - {str(e_row)}")
            
            if imported_count > 0: db.session.commit()
            flash(f"Successfully imported {imported_count} students. Skipped {skipped_count} rows.", "success" if imported_count > 0 else "info")
            if error_rows:
                flash("Errors/Skipped Rows Details:", "warning");
                for err in error_rows[:15]: flash(err, "danger")
                if len(error_rows) > 15: flash(f"...and {len(error_rows) - 15} more errors not shown.", "warning")
            return redirect(url_for('admin.list_students'))
        except pd.errors.EmptyDataError: flash("The uploaded CSV file is empty.", "danger")
        except Exception as e: db.session.rollback(); flash(f"An error occurred during CSV processing: {str(e)}", "danger"); current_app.logger.error(f"Student CSV Import Error: {e}", exc_info=True)

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
            required_cols = { 'class_name': 'class_name', 'subject_identifier': 'subject_identifier' }; optional_cols = { 'teacher_identifier': 'teacher_identifier', 'schedule_details': 'schedule_details', 'academic_year': 'academic_year', 'start_date': 'start_date', 'end_date': 'end_date' }
            df.columns = df.columns.str.lower().str.strip()
            missing_required = [col_display for col_key, col_display in required_cols.items() if col_key not in df.columns]
            if missing_required: flash(f"CSV file is missing required columns: {', '.join(missing_required)}.", "danger"); return render_template('admin/import_classes_csv.html', form=form, title="Import Subject Classes from CSV")
            
            imported_count = 0; skipped_count = 0; error_rows = []
            for index, row_data in df.iterrows():
                row_series = pd.Series(row_data)
                try:
                    class_name = str(row_series[required_cols['class_name']]).strip(); subject_identifier = str(row_series[required_cols['subject_identifier']]).strip()
                    if not class_name or not subject_identifier: skipped_count += 1; error_rows.append(f"Row {index+2}: Missing required field class_name or subject_identifier."); continue
                    
                    subject = Subject.query.filter(Subject.name.ilike(subject_identifier)).first()
                    if not subject:
                        try: subject_id_int = int(subject_identifier); subject = Subject.query.get(subject_id_int)
                        except ValueError: subject = None
                    if not subject: skipped_count += 1; error_rows.append(f"Row {index+2}: Subject '{subject_identifier}' not found."); continue
                    
                    teacher_user_id = None
                    if optional_cols['teacher_identifier'] in row_series:
                        teacher_identifier = str(row_series.get(optional_cols['teacher_identifier'], '')).strip()
                        if teacher_identifier and teacher_identifier.lower() not in ['nan', '']:
                            teacher = User.query.filter((User.username.ilike(teacher_identifier) | User.email.ilike(teacher_identifier)) & (User.role == UserRole.TEACHER)).first()
                            if not teacher:
                                try: teacher_id_int = int(teacher_identifier); teacher = User.query.filter_by(id=teacher_id_int, role=UserRole.TEACHER).first()
                                except ValueError: teacher = None
                            if teacher: teacher_user_id = teacher.id
                            else: error_rows.append(f"Row {index+2}: Teacher '{teacher_identifier}' not found or not a Teacher role. Class will be created without a teacher if other fields are valid.")
                    
                    if SubjectClass.query.filter(SubjectClass.name.ilike(class_name)).first(): skipped_count += 1; error_rows.append(f"Row {index+2}: Class name '{class_name}' already exists."); continue
                    
                    schedule_details_from_csv = str(row_series.get(optional_cols['schedule_details'], '')).strip() if optional_cols['schedule_details'] in row_series else None
                    
                    academic_year = str(row_series.get(optional_cols['academic_year'], '')).strip() if optional_cols['academic_year'] in row_series else None
                    
                    start_date_str = str(row_series.get(optional_cols['start_date'], '')).strip() if optional_cols['start_date'] in row_series else None; start_date = None
                    if start_date_str and start_date_str.lower() not in ['nan', '']:
                        try: start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                        except ValueError:
                            try: start_date = datetime.strptime(start_date_str, '%d/%m/%Y').date()
                            except ValueError: error_rows.append(f"Row {index+2}: Invalid start_date format for '{start_date_str}'. Use YYYY-MM-DD or DD/MM/YYYY. Date ignored.")
                    
                    end_date_str = str(row_series.get(optional_cols['end_date'], '')).strip() if optional_cols['end_date'] in row_series else None; end_date = None
                    if end_date_str and end_date_str.lower() not in ['nan', '']:
                        try: end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                        except ValueError:
                            try: end_date = datetime.strptime(end_date_str, '%d/%m/%Y').date()
                            except ValueError: error_rows.append(f"Row {index+2}: Invalid end_date format for '{end_date_str}'. Use YYYY-MM-DD or DD/MM/YYYY. Date ignored.")
                    
                    if start_date and end_date and end_date < start_date: error_rows.append(f"Row {index+2}: End date ({end_date_str}) cannot be before start date ({start_date_str}). Dates ignored."); start_date, end_date = None, None
                    
                    new_class = SubjectClass(name=class_name, subject_id=subject.id, teacher_user_id=teacher_user_id, 
                                             schedule_details=schedule_details_from_csv if schedule_details_from_csv and schedule_details_from_csv.lower() != 'nan' else None, 
                                             academic_year=academic_year if academic_year and academic_year.lower() != 'nan' else None, 
                                             start_date=start_date, end_date=end_date)
                    db.session.add(new_class)
                    # TODO: If CSV for classes includes detailed schedule (day, time for multiple entries),
                    # parse it here and create ClassSchedule objects linked to new_class.
                    imported_count += 1
                except Exception as e_row: skipped_count += 1; error_rows.append(f"Row {index+2}: Error processing row - {str(e_row)}")
            
            if imported_count > 0: db.session.commit()
            flash(f"Successfully imported {imported_count} classes. Skipped {skipped_count} rows.", "success" if imported_count > 0 else "info")
            if error_rows:
                flash("Issues Encountered During Import:", "warning");
                for err in error_rows[:15]: flash(err, "danger")
                if len(error_rows) > 15: flash(f"...and {len(error_rows) - 15} more issues not shown.", "warning")
            return redirect(url_for('admin.list_subject_classes'))
        except pd.errors.EmptyDataError: flash("The uploaded CSV file is empty.", "danger")
        except Exception as e: db.session.rollback(); flash(f"An error occurred during CSV processing: {str(e)}", "danger"); current_app.logger.error(f"Class CSV Import Error: {e}", exc_info=True)
    return render_template('admin/import_classes_csv.html', form=form, title="Import Subject Classes from CSV")

# --- Backup Routes ---
# ... (Backup routes remain the same) ...
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
    if not os.path.isabs(db_path_part):
        db_file_path_instance = os.path.join(current_app.instance_path, db_path_part)
        if os.path.exists(db_file_path_instance):
            db_file_path = db_file_path_instance
        else: 
             db_file_path = os.path.join(current_app.root_path, db_path_part)
    else:
        db_file_path = db_path_part
    db_file_path = os.path.normpath(db_file_path)

    if not os.path.exists(db_file_path):
        flash(f"Database file not found at expected path: {db_file_path}", "danger"); return redirect(url_for('admin.backup_management'))
    
    backup_dir = get_backup_dir(); timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"attendance_app_backup_{timestamp}.db"; backup_filepath = os.path.join(backup_dir, backup_filename)
    try: shutil.copy2(db_file_path, backup_filepath); flash(f"Backup created: {backup_filename}", "success")
    except Exception as e: flash(f"Error creating backup: {str(e)}", "danger"); current_app.logger.error(f"Error creating backup: {e}", exc_info=True)
    return redirect(url_for('admin.backup_management'))

@admin.route('/backup/download/<path:filename>')
@login_required
@admin_required
def download_backup(filename):
    backup_dir = get_backup_dir()
    safe_filename = secure_filename(filename)
    if not safe_filename or safe_filename != filename :
        abort(400, "Invalid filename.")
    try: return send_from_directory(backup_dir, safe_filename, as_attachment=True)
    except FileNotFoundError: abort(404)
    except Exception as e: 
        current_app.logger.error(f"Error downloading backup {safe_filename}: {e}", exc_info=True)
        flash(f"Error downloading backup: {str(e)}", "danger"); 
        return redirect(url_for('admin.backup_management'))

# --- User Management Routes (Admin Level) ---
# ... (User management routes remain the same) ...
@admin.route('/users')
@login_required
@admin_required 
def list_all_users():
    users = User.query.order_by(User.username).all()
    return render_template('admin/users.html', users=users, title="Manage All Users")

@admin.route('/users/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_user_admin():
    form = UserAdminForm() 
    if form.validate_on_submit():
        new_user = User(
            username=form.username.data, email=form.email.data,
            first_name=form.first_name.data, last_name=form.last_name.data,
            role=UserRole(form.role.data), is_active=form.is_active.data
        )
        new_user.set_password(form.password.data)
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
    user_to_edit = User.query.get_or_404(user_id)
    if user_to_edit.role == UserRole.SUPERUSER and not current_user.is_superuser:
        flash("Only Superusers can edit other Superusers.", "danger")
        return redirect(url_for('admin.list_all_users'))
        
    form = UserAdminForm(editing_user=user_to_edit, obj=user_to_edit) 

    if form.validate_on_submit():
        can_proceed = True
        if user_to_edit.id == current_user.id:
            if UserRole(form.role.data) not in [UserRole.ADMIN, UserRole.SUPERUSER] and current_user.role == UserRole.ADMIN :
                flash("Administrators cannot demote themselves from Admin/Superuser role.", "danger")
                form.role.data = current_user.role.value 
                can_proceed = False
            if not form.is_active.data:
                flash("Administrators cannot deactivate their own account.", "danger")
                form.is_active.data = True 
                can_proceed = False
        
        if user_to_edit.role == UserRole.SUPERUSER and not current_user.is_superuser and UserRole(form.role.data) != UserRole.SUPERUSER:
             flash("Only a Superuser can change the role of another Superuser.", "danger")
             form.role.data = UserRole.SUPERUSER.value 
             can_proceed = False
        
        if can_proceed:
            user_to_edit.username = form.username.data
            user_to_edit.email = form.email.data
            user_to_edit.first_name = form.first_name.data
            user_to_edit.last_name = form.last_name.data
            user_to_edit.role = UserRole(form.role.data)
            user_to_edit.is_active = form.is_active.data

            if form.password.data: 
                user_to_edit.set_password(form.password.data)
            try:
                db.session.commit()
                flash(f'User {user_to_edit.username} updated successfully!', 'success')
                return redirect(url_for('admin.list_all_users'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating user: {str(e)}', 'danger')
                current_app.logger.error(f"Error editing user {user_id} by admin: {e}", exc_info=True)
    
    if request.method == 'GET': 
        form.role.data = user_to_edit.role.value 

    return render_template('admin/user_form_admin.html', form=form, title="Edit User", 
                           legend=f"Edit User: {user_to_edit.username}", user_being_edited=user_to_edit)

@admin.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user_admin(user_id):
    user_to_delete = User.query.get_or_404(user_id)
    if user_to_delete.id == current_user.id:
        flash("You cannot delete your own account.", "danger")
        return redirect(url_for('admin.list_all_users'))
    if user_to_delete.role == UserRole.SUPERUSER and not current_user.is_superuser:
        flash("Only Superusers can delete other Superusers.", "danger")
        return redirect(url_for('admin.list_all_users'))
    if user_to_delete.role == UserRole.TEACHER and user_to_delete.classes_taught.first():
        flash(f"Cannot delete teacher {user_to_delete.username} as they are assigned to classes. Please reassign classes first or deactivate the user.", "warning")
        return redirect(url_for('admin.list_all_users'))
    try:
        db.session.delete(user_to_delete)
        db.session.commit()
        flash(f'User {user_to_delete.username} has been deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error processing user account: {str(e)}', 'danger')
        current_app.logger.error(f"Error deleting/deactivating user {user_id} by admin: {e}", exc_info=True)
    return redirect(url_for('admin.list_all_users'))

# --- Holiday Management Routes ---
@admin.route('/holidays', methods=['GET'])
@login_required
@staff_required 
def list_holidays():
    page = request.args.get('page', 1, type=int)
    holidays = Holiday.query.order_by(Holiday.date.asc()).paginate(page=page, per_page=15)
    return render_template('admin/list_holidays.html', holidays=holidays, title="Manage Holidays & Events")

@admin.route('/holidays/add', methods=['GET', 'POST'])
@login_required
@staff_required 
def add_holiday():
    form = HolidayForm()
    if form.validate_on_submit():
        existing_holiday = Holiday.query.filter_by(date=form.date.data).first()
        if existing_holiday:
            flash(f'A holiday or event named "{existing_holiday.name}" already exists for this date ({form.date.data.strftime("%Y-%m-%d")}). Please edit the existing entry or choose a different date.', 'warning')
        else:
            holiday = Holiday(name=form.name.data,
                              date=form.date.data,
                              type=form.type.data,
                              description=form.description.data)
            try:
                db.session.add(holiday)
                db.session.commit()
                flash('Holiday/Event added successfully!', 'success')
                return redirect(url_for('admin.list_holidays'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error adding holiday/event: {str(e)}', 'danger')
                current_app.logger.error(f"Error adding holiday: {e}", exc_info=True)
    return render_template('admin/holiday_form.html', form=form, title="Add New Holiday/Event", legend="Add New Holiday/Event")

@admin.route('/holidays/edit/<int:holiday_id>', methods=['GET', 'POST'])
@login_required
@staff_required 
def edit_holiday(holiday_id):
    holiday = Holiday.query.get_or_404(holiday_id)
    form = HolidayForm(obj=holiday) 
    if form.validate_on_submit():
        if form.date.data != holiday.date: 
            existing_holiday_on_new_date = Holiday.query.filter(Holiday.date == form.date.data, Holiday.id != holiday.id).first()
            if existing_holiday_on_new_date:
                flash(f'Another holiday/event ("{existing_holiday_on_new_date.name}") already exists for the new date {form.date.data.strftime("%Y-%m-%d")}. Please choose a different date.', 'warning')
                return render_template('admin/holiday_form.html', form=form, title="Edit Holiday/Event", legend=f"Edit: {holiday.name}", holiday=holiday)
        
        holiday.name = form.name.data
        holiday.date = form.date.data
        holiday.type = form.type.data
        holiday.description = form.description.data
        try:
            db.session.commit()
            flash('Holiday/Event updated successfully!', 'success')
            return redirect(url_for('admin.list_holidays'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating holiday/event: {str(e)}', 'danger')
            current_app.logger.error(f"Error updating holiday {holiday_id}: {e}", exc_info=True)
            
    return render_template('admin/holiday_form.html', form=form, title="Edit Holiday/Event", legend=f"Edit: {holiday.name}", holiday=holiday)

@admin.route('/holidays/delete/<int:holiday_id>', methods=['POST'])
@login_required
@staff_required 
def delete_holiday(holiday_id):
    holiday = Holiday.query.get_or_404(holiday_id)
    try:
        db.session.delete(holiday)
        db.session.commit()
        flash(f'Holiday/Event "{holiday.name}" deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting holiday/event: {str(e)}', 'danger')
        current_app.logger.error(f"Error deleting holiday {holiday_id}: {e}", exc_info=True)
    return redirect(url_for('admin.list_holidays'))


# --- System Log Viewer Route ---
@admin.route('/system-logs')
@login_required
@admin_required 
def view_system_logs():
    log_dir = os.path.join(current_app.instance_path, 'logs') 
    log_file_path_app = os.path.join(log_dir, 'attendance_app.log')
    log_content = {}
    try:
        with open(log_file_path_app, 'r') as f:
            lines = f.readlines()
            log_content['app_log'] = "".join(lines[-200:]) 
    except FileNotFoundError:
        log_content['app_log'] = f"Application log file not found at: {log_file_path_app}"
        current_app.logger.warning(f"Log file not found by admin viewer: {log_file_path_app}")
    except Exception as e:
        log_content['app_log'] = f"Error reading application log: {str(e)}"
        current_app.logger.error(f"Error reading app log for display: {e}", exc_info=True)
    return render_template('admin/system_logs.html', 
                           log_content=log_content, 
                           title="View System Logs")

@admin.route('/system-logs/download/<log_type>')
@login_required
@admin_required
def download_log_file(log_type):
    log_dir = os.path.join(current_app.instance_path, 'logs')
    log_filename = None
    if log_type == "app":
        log_filename = "attendance_app.log"
    # Add more log types here if needed e.g. gunicorn_error
    # elif log_type == "gunicorn_error":
    #     log_filename = "gunicorn_error.log"

    if log_filename:
        safe_log_filename = secure_filename(log_filename) 
        log_file_path = os.path.join(log_dir, safe_log_filename)
        if os.path.exists(log_file_path):
            try:
                return send_file(log_file_path, as_attachment=True)
            except Exception as e:
                flash(f"Error downloading log file {safe_log_filename}: {str(e)}", "danger")
                current_app.logger.error(f"Error downloading log {safe_log_filename}: {e}", exc_info=True)
        else:
            flash(f"Log file {safe_log_filename} not found at {log_dir}.", "danger")
            current_app.logger.warning(f"Download attempt for non-existent log: {log_file_path}")
    else:
        flash("Invalid log type specified for download.", "danger")
    return redirect(url_for('admin.view_system_logs'))

