# app/teacher/routes.py
from flask import render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from wtforms.validators import Length 
from . import teacher 
from app.decorators import teacher_required 
from app.models import User, SubjectClass, UserRole, Student, Attendance, AttendanceStatus 
from app.teacher.forms import MarkAttendanceForm, StudentAttendanceEntryForm 
from app import db
from datetime import date, datetime, timedelta
from collections import defaultdict # For summarizing attendance

@teacher.route('/')
@login_required
@teacher_required
def teacher_dashboard():
    return redirect(url_for('teacher.my_classes'))

@teacher.route('/my-classes')
@login_required
@teacher_required
def my_classes():
    assigned_classes = current_user.classes_taught.options(
        db.joinedload(SubjectClass.subject_taught)
    ).order_by(SubjectClass.name).all()
    
    return render_template('teacher/my_classes.html', 
                           classes=assigned_classes, 
                           title="My Classes")

# Helper function to parse day of week from schedule string (already exists from previous step)
def parse_scheduled_day(schedule_details_str):
    if not schedule_details_str or len(schedule_details_str) < 3:
        return None
    day_abbr = schedule_details_str[:3].lower()
    days_map = {
        'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6
    }
    return days_map.get(day_abbr)

@teacher.route('/class/<int:class_id>/attendance/mark', methods=['GET', 'POST'])
@login_required
@teacher_required
def mark_attendance(class_id):
    subject_class = SubjectClass.query.options(
        db.joinedload(SubjectClass.subject_taught),
        db.joinedload(SubjectClass.teacher_user)
    ).get_or_404(class_id)

    if subject_class.teacher_user_id != current_user.id:
        flash("You are not authorized to mark attendance for this class.", "danger")
        return redirect(url_for('teacher.my_classes'))

    form = MarkAttendanceForm()
    today = date.today()
    scheduled_weekday = parse_scheduled_day(subject_class.schedule_details)

    if scheduled_weekday is None:
        default_class_date_for_week = today
    else:
        days_difference = scheduled_weekday - today.weekday()
        default_class_date_for_week = today + timedelta(days=days_difference)

    selected_date_str = request.args.get('attendance_date')
    if selected_date_str:
        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
            if scheduled_weekday is not None and selected_date.weekday() != scheduled_weekday:
                flash(f"Attendance for this class is on {subject_class.schedule_details[:3]}. Selected date is not a valid class day. Showing default date instead.", "warning")
                selected_date = default_class_date_for_week
        except ValueError:
            flash("Invalid date format from picker. Showing default date.", "warning")
            selected_date = default_class_date_for_week
    else:
        if request.method == 'POST' and form.attendance_date.data:
             selected_date = form.attendance_date.data
        else:
            selected_date = default_class_date_for_week
    form.attendance_date.data = selected_date

    if request.method == 'POST' and form.validate_on_submit():
        if scheduled_weekday is not None and form.attendance_date.data.weekday() != scheduled_weekday:
            flash(f"Submission error: Attendance for this class should be on a {subject_class.schedule_details[:3]}. Please select a valid date.", "danger")
        else:
            try:
                for student_entry_data in form.students_attendance.data:
                    student_id = student_entry_data['student_id']
                    status_val = student_entry_data['status']
                    remarks = student_entry_data['remarks']
                    attendance_record = Attendance.query.filter_by(
                        student_id=student_id, class_id=class_id, attendance_date=selected_date
                    ).first()
                    if attendance_record:
                        attendance_record.status = AttendanceStatus(status_val) 
                        attendance_record.remarks = remarks
                        attendance_record.recorded_by_user_id = current_user.id
                        attendance_record.recorded_at = datetime.utcnow()
                    else:
                        attendance_record = Attendance(
                            student_id=student_id, class_id=class_id,
                            attendance_date=selected_date, status=AttendanceStatus(status_val),
                            remarks=remarks, recorded_by_user_id=current_user.id
                        )
                        db.session.add(attendance_record)
                db.session.commit()
                flash(f'Attendance for {selected_date.strftime("%A, %B %d, %Y")} saved successfully!', 'success')
                return redirect(url_for('teacher.mark_attendance', class_id=class_id, attendance_date=selected_date.strftime('%Y-%m-%d')))
            except Exception as e:
                db.session.rollback()
                flash(f'Error saving attendance: {str(e)}', 'danger')

    while len(form.students_attendance) > 0:
        form.students_attendance.pop_entry()
    enrolled_students = subject_class.students_enrolled.filter(Student.is_active==True).order_by(Student.last_name, Student.first_name).all()
    for student in enrolled_students:
        existing_attendance = Attendance.query.filter_by(
            student_id=student.id, class_id=class_id, attendance_date=selected_date
        ).first()
        student_form_entry = StudentAttendanceEntryForm()
        student_form_entry.student_id = student.id
        if existing_attendance:
            student_form_entry.status = existing_attendance.status.value 
            student_form_entry.remarks = existing_attendance.remarks
        else:
            student_form_entry.status = AttendanceStatus.PRESENT.value 
        form.students_attendance.append_entry(student_form_entry)
        
    return render_template('teacher/mark_attendance.html', 
                           form=form, 
                           subject_class=subject_class, 
                           title=f"Mark Attendance for {subject_class.name}",
                           selected_date_for_display=selected_date, 
                           enrolled_students_for_template=enrolled_students,
                           scheduled_weekday_num=scheduled_weekday)

# --- New Class Attendance Report Route ---
@teacher.route('/class/<int:class_id>/attendance-report')
@login_required
@teacher_required # Or a more general permission if admins/staff can also view
def class_attendance_report(class_id):
    """
    Displays an attendance report/summary for a specific class.
    """
    subject_class = SubjectClass.query.options(
        db.joinedload(SubjectClass.subject_taught),
        db.joinedload(SubjectClass.teacher_user) # Eager load teacher
    ).get_or_404(class_id)

    # Authorization: Ensure teacher is assigned or user is admin/staff
    # For now, sticking to teacher_required. Modify if other roles need access.
    if not current_user.is_admin and not current_user.is_staff and subject_class.teacher_user_id != current_user.id :
        flash("You are not authorized to view the report for this class.", "danger")
        return redirect(url_for('teacher.my_classes'))

    # Get all enrolled students for this class
    enrolled_students = subject_class.students_enrolled.filter(Student.is_active==True).order_by(Student.last_name, Student.first_name).all()

    # Get all attendance records for this class
    all_attendance_records = Attendance.query.filter_by(class_id=class_id).all()

    # Process attendance data to create a summary per student
    student_summary_data = {}
    for student in enrolled_students:
        student_summary_data[student.id] = {
            'student_obj': student,
            'total_present': 0,
            'total_absent': 0,
            'total_late': 0,
            'total_excused': 0,
            'total_sessions_recorded': 0 # Count of days where attendance was taken for this student
        }

    # Tally up attendance statuses for each student
    # This assumes attendance is recorded for each student for each class session date.
    # A more advanced report might consider the total number of unique class session dates.
    unique_class_session_dates = db.session.query(Attendance.attendance_date).filter_by(class_id=class_id).distinct().count()


    for record in all_attendance_records:
        if record.student_id in student_summary_data:
            summary = student_summary_data[record.student_id]
            summary['total_sessions_recorded'] += 1 # Increment if a record exists for this student on a day
            if record.status == AttendanceStatus.PRESENT:
                summary['total_present'] += 1
            elif record.status == AttendanceStatus.ABSENT:
                summary['total_absent'] += 1
            elif record.status == AttendanceStatus.LATE:
                summary['total_late'] += 1
            elif record.status == AttendanceStatus.EXCUSED:
                summary['total_excused'] += 1
    
    # For a more accurate percentage, we might need to know total possible sessions.
    # For now, 'total_sessions_recorded' is specific to when this student had a record.
    # If a student enrolls late, they won't have records for earlier dates.
    # `unique_class_session_dates` gives a count of distinct dates for which *any* attendance was recorded for this class.

    return render_template('teacher/class_attendance_report.html',
                           subject_class=subject_class,
                           student_summary_data=student_summary_data.values(), # Pass as a list of dicts
                           unique_class_session_dates=unique_class_session_dates,
                           title=f"Attendance Report for {subject_class.name}")

