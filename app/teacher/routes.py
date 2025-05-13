# app/teacher/routes.py
from flask import render_template, request, redirect, url_for, flash, abort, current_app
from flask_login import login_required, current_user # current_user is used for authorization
from . import teacher 
from app.decorators import teacher_required # This might be used by other teacher-specific routes
# from app.decorators import admin_required, staff_required # Not directly used here, but good to have if needed elsewhere
from app.models import User, SubjectClass, Student, Attendance, Holiday, ATTENDANCE_STATUS_CHOICES 
from app.teacher.forms import MarkAttendanceForm, StudentAttendanceEntryForm 
from app import db
from datetime import date, datetime, timedelta 
from collections import defaultdict
import calendar 

# --- Existing Teacher Routes ---
@teacher.route('/')
@login_required
@teacher_required # This route is likely teacher-specific for their main dashboard/class list
def teacher_dashboard():
    return redirect(url_for('teacher.my_classes'))

@teacher.route('/my-classes')
@login_required
@teacher_required # This route is for a teacher to see *their own* classes
def my_classes():
    assigned_classes = current_user.classes_taught.options(
        db.joinedload(SubjectClass.subject_taught)
    ).order_by(SubjectClass.name).all()
    
    today = date.today()
    upcoming_holidays_query = Holiday.query.filter(Holiday.date >= today).order_by(Holiday.date.asc())
    upcoming_holidays = upcoming_holidays_query.limit(5).all() 
    
    return render_template('teacher/my_classes.html', 
                           classes=assigned_classes, 
                           upcoming_holidays=upcoming_holidays,
                           title="My Classes & Dashboard")

def parse_scheduled_day(schedule_details_str):
    if not schedule_details_str or len(schedule_details_str) < 3:
        return None
    day_abbr = schedule_details_str[:3].lower()
    days_map = { 'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6 }
    return days_map.get(day_abbr)

# --- MODIFIED mark_attendance route ---
@teacher.route('/class/<int:class_id>/attendance/mark', methods=['GET', 'POST'])
@login_required # Keep @login_required
# REMOVED @teacher_required decorator
def mark_attendance(class_id):
    subject_class = SubjectClass.query.options(
        db.joinedload(SubjectClass.subject_taught),
        db.joinedload(SubjectClass.teacher_user)
    ).get_or_404(class_id)

    # --- UPDATED Authorization Check ---
    # Allows assigned teacher, admin, or staff to mark/view attendance for this class
    can_access = False
    if current_user.is_authenticated:
        if current_user.is_admin or current_user.is_staff:
            can_access = True
        elif current_user.is_teacher and subject_class.teacher_user_id == current_user.id:
            can_access = True
    
    if not can_access:
        flash("You are not authorized to mark attendance for this class.", "danger")
        # Redirect appropriately based on user's likely role if they are logged in
        if current_user.is_authenticated and current_user.is_teacher:
            return redirect(url_for('teacher.my_classes'))
        else: # For other authenticated users or if role is unclear, send to main dashboard
            return redirect(url_for('main.dashboard')) 
    # --- END UPDATED Authorization Check ---

    form = MarkAttendanceForm()
    today = date.today()
    scheduled_weekday = parse_scheduled_day(subject_class.schedule_details)

    default_class_date_for_week = today
    if scheduled_weekday is not None:
        days_difference = scheduled_weekday - today.weekday()
        default_class_date_for_week = today + timedelta(days=days_difference)

    selected_date_str = request.args.get('attendance_date')
    if selected_date_str:
        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
            # Optional: Add back weekday check if you want to warn, but allow override for admin/staff
            # if scheduled_weekday is not None and selected_date.weekday() != scheduled_weekday and not (current_user.is_admin or current_user.is_staff):
            #     flash(f"Attendance for this class is typically on {subject_class.schedule_details[:3]}. Selected date is not a scheduled class day. Showing default date instead.", "warning")
            #     selected_date = default_class_date_for_week
        except ValueError:
            flash("Invalid date format from picker. Showing default date.", "warning")
            selected_date = default_class_date_for_week
    else:
        if request.method == 'POST' and form.attendance_date.data:
             selected_date = form.attendance_date.data
        else:
            selected_date = default_class_date_for_week
    
    form.attendance_date.data = selected_date

    # Check if the selected date is a holiday
    holiday_on_selected_date = None
    if selected_date:
        holiday_on_selected_date = Holiday.query.filter_by(date=selected_date).first()

    if request.method == 'POST' and form.validate_on_submit():
        # Optional: Re-check weekday if strict for teachers but not admin/staff
        # if scheduled_weekday is not None and form.attendance_date.data.weekday() != scheduled_weekday and not (current_user.is_admin or current_user.is_staff):
        #     flash(f"Submission error: Attendance for this class should be on a {subject_class.schedule_details[:3]}. Please select a valid date.", "danger")
        # else:
        try:
            for student_entry_data in form.students_attendance.data:
                student_id = student_entry_data['student_id']
                status_val = student_entry_data['status'] 
                remarks = student_entry_data['remarks']
                
                attendance_record = Attendance.query.filter_by(
                    student_id=student_id, 
                    subject_class_id=class_id, 
                    date=selected_date # Use the determined selected_date
                ).first()
                
                if attendance_record:
                    attendance_record.status = status_val 
                    attendance_record.remarks = remarks
                    attendance_record.recorded_by_user_id = current_user.id
                else:
                    attendance_record = Attendance(
                        student_id=student_id, 
                        subject_class_id=class_id, 
                        date=selected_date, 
                        status=status_val, 
                        remarks=remarks, 
                        recorded_by_user_id=current_user.id
                    )
                    db.session.add(attendance_record)
            db.session.commit()
            flash(f'Attendance for {selected_date.strftime("%A, %B %d, %Y")} saved successfully!', 'success')
            return redirect(url_for('teacher.mark_attendance', class_id=class_id, attendance_date=selected_date.strftime('%Y-%m-%d')))
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving attendance: {str(e)}', 'danger')
            current_app.logger.error(f"Error in mark_attendance POST: {e}", exc_info=True)

    # Populate form for GET request or if POST validation failed
    while len(form.students_attendance) > 0:
        form.students_attendance.pop_entry()

    enrolled_students = subject_class.students_enrolled.filter(Student.is_active==True).order_by(Student.last_name, Student.first_name).all()
    for student in enrolled_students:
        existing_attendance = Attendance.query.filter_by(
            student_id=student.id, 
            subject_class_id=class_id, 
            date=selected_date
        ).first()
        
        student_form_entry = StudentAttendanceEntryForm()
        student_form_entry.student_id = student.id
        
        if existing_attendance:
            student_form_entry.status = existing_attendance.status 
            student_form_entry.remarks = existing_attendance.remarks
        elif holiday_on_selected_date: # If it's a holiday and no record exists, default to a holiday status
             if holiday_on_selected_date.type == "Public Holiday":
                 student_form_entry.status = 'public_holiday'
             elif holiday_on_selected_date.type == "School Holiday":
                 student_form_entry.status = 'school_holiday'
             else: # Default for other event types on a holiday if no record
                 student_form_entry.status = 'present' # Or 'absent' or ''
        else:
            student_form_entry.status = 'present' 
        form.students_attendance.append_entry(student_form_entry)
        
    return render_template('teacher/mark_attendance.html', 
                           form=form, 
                           subject_class=subject_class, 
                           title=f"Mark Attendance for {subject_class.name}",
                           selected_date_for_display=selected_date, 
                           enrolled_students_for_template=enrolled_students,
                           scheduled_weekday_num=scheduled_weekday,
                           holiday_info=holiday_on_selected_date)


# --- class_attendance_report route ---
@teacher.route('/class/<int:class_id>/attendance-report')
@login_required
# @teacher_required # REMOVE if admins/staff should also access this directly
def class_attendance_report(class_id):
    subject_class = SubjectClass.query.options(
        db.joinedload(SubjectClass.subject_taught),
        db.joinedload(SubjectClass.teacher_user) 
    ).get_or_404(class_id)

    # UPDATED Authorization Check
    can_access_report = False
    if current_user.is_authenticated:
        if current_user.is_admin or current_user.is_staff:
            can_access_report = True
        elif current_user.is_teacher and subject_class.teacher_user_id == current_user.id:
            can_access_report = True
            
    if not can_access_report:
        flash("You are not authorized to view the report for this class.", "danger")
        if current_user.is_authenticated and current_user.is_teacher:
            return redirect(url_for('teacher.my_classes'))
        else:
            return redirect(url_for('main.dashboard'))

    enrolled_students = subject_class.students_enrolled.filter(Student.is_active==True).order_by(Student.last_name, Student.first_name).all()
    all_attendance_records = Attendance.query.filter_by(subject_class_id=class_id).all()

    student_summary_data = {}
    for student in enrolled_students:
        student_summary_data[student.id] = {
            'student_obj': student,
            'total_present': 0, 'total_absent': 0, 'total_late': 0, 'total_excused': 0,
            'total_public_holiday': 0, 'total_school_holiday': 0, 
            'total_sessions_recorded': 0
        }

    unique_class_session_dates = db.session.query(Attendance.date).filter_by(subject_class_id=class_id).distinct().count()

    for record in all_attendance_records:
        if record.student_id in student_summary_data:
            summary = student_summary_data[record.student_id]
            summary['total_sessions_recorded'] += 1
            if record.status == 'present': summary['total_present'] += 1
            elif record.status == 'absent': summary['total_absent'] += 1
            elif record.status == 'late': summary['total_late'] += 1
            elif record.status == 'excused': summary['total_excused'] += 1
            elif record.status == 'public_holiday': summary['total_public_holiday'] += 1
            elif record.status == 'school_holiday': summary['total_school_holiday'] += 1
    
    return render_template('teacher/class_attendance_report.html',
                           subject_class=subject_class,
                           student_summary_data=student_summary_data.values(), 
                           unique_class_session_dates=unique_class_session_dates,
                           title=f"Attendance Report for {subject_class.name}")

# --- view_all_holidays route ---
@teacher.route('/holidays')
@login_required
@teacher_required # This page is fine to be teacher-specific or could be moved to main
def view_all_holidays():
    year = request.args.get('year', default=date.today().year, type=int)
    holidays_for_year = Holiday.query.filter(
        db.extract('year', Holiday.date) == year
    ).order_by(Holiday.date.asc()).all()
    
    available_years_query = db.session.query(db.extract('year', Holiday.date).label('year')).distinct().order_by(db.desc('year'))
    available_years = [y.year for y in available_years_query.all()]

    if not available_years and not holidays_for_year : 
        available_years = [date.today().year] 
    elif year not in available_years and available_years: 
         if date.today().year in available_years: 
            year = date.today().year
         else: 
            year = available_years[0] if available_years else date.today().year
         holidays_for_year = Holiday.query.filter(
            db.extract('year', Holiday.date) == year
         ).order_by(Holiday.date.asc()).all()

    return render_template('teacher/all_holidays.html', 
                           holidays=holidays_for_year, 
                           selected_year=year,
                           available_years=available_years,
                           title=f"School Holidays & Events for {year}")

# --- monthly_class_attendance_matrix route ---
def get_scheduled_class_dates_for_month(subject_class, year, month):
    scheduled_dates = []
    if not subject_class.schedule_details:
        # Fallback or integrate with ClassSchedule model if it's populated
        # For now, simple parsing of schedule_details
        single_scheduled_day_int = parse_scheduled_day(subject_class.schedule_details)
        if single_scheduled_day_int is None:
            current_app.logger.warning(f"Could not determine scheduled weekdays for class {subject_class.id} from '{subject_class.schedule_details}' for monthly matrix.")
            return []
        scheduled_weekdays = [single_scheduled_day_int]
    else: # More robust parsing if schedule_details can contain multiple days
        day_map_str_to_int = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6}
        scheduled_weekdays = []
        details_lower = subject_class.schedule_details.lower()
        for day_str, day_int in day_map_str_to_int.items():
            if day_str in details_lower:
                scheduled_weekdays.append(day_int)
        if not scheduled_weekdays: # Fallback if complex parsing fails
             single_scheduled_day_int = parse_scheduled_day(subject_class.schedule_details)
             if single_scheduled_day_int is not None: scheduled_weekdays.append(single_scheduled_day_int)
             else:
                current_app.logger.warning(f"Could not determine scheduled weekdays for class {subject_class.id} from '{subject_class.schedule_details}' for monthly matrix (complex parse failed).")
                return []

    num_days_in_month = calendar.monthrange(year, month)[1]
    for day_num in range(1, num_days_in_month + 1):
        try:
            current_date = date(year, month, day_num)
            if current_date.weekday() in scheduled_weekdays:
                scheduled_dates.append(current_date)
        except ValueError: 
            continue
    return sorted(list(set(scheduled_dates))) 

@teacher.route('/class/<int:class_id>/attendance/monthly', methods=['GET'])
@login_required
# REMOVED @teacher_required from here
def monthly_class_attendance_matrix(class_id):
    subject_class = SubjectClass.query.options(
        db.joinedload(SubjectClass.subject_taught),
        db.joinedload(SubjectClass.teacher_user)
    ).get_or_404(class_id)

    # UPDATED Authorization Check
    can_access_matrix = False
    if current_user.is_authenticated:
        if current_user.is_admin or current_user.is_staff:
            can_access_matrix = True
        elif current_user.is_teacher and subject_class.teacher_user_id == current_user.id:
            can_access_matrix = True
            
    if not can_access_matrix:
        flash("You are not authorized to view this attendance matrix.", "danger")
        if current_user.is_authenticated and current_user.is_teacher:
            return redirect(url_for('teacher.my_classes'))
        else:
            return redirect(url_for('main.dashboard'))

    try:
        year = request.args.get('year', default=date.today().year, type=int)
        month = request.args.get('month', default=date.today().month, type=int)
        if not (1 <= month <= 12):
            month = date.today().month
            flash("Invalid month selected, defaulting to current month.", "warning")
        if not (2000 <= year <= date.today().year + 5): 
            year = date.today().year
            flash("Invalid year selected, defaulting to current year.", "warning")
    except ValueError:
        year = date.today().year
        month = date.today().month
        flash("Invalid month/year parameters, defaulting to current.", "warning")

    class_session_dates = get_scheduled_class_dates_for_month(subject_class, year, month)
    enrolled_students = subject_class.students_enrolled.filter(Student.is_active==True).order_by(Student.last_name, Student.first_name).all()
    
    attendance_records_query = Attendance.query.filter(
        Attendance.subject_class_id == class_id,
        Attendance.student_id.in_([s.id for s in enrolled_students] if enrolled_students else []),
        Attendance.date.in_(class_session_dates) if class_session_dates else []
    ).all()

    attendance_matrix = defaultdict(dict)
    for record in attendance_records_query:
        attendance_matrix[record.student_id][record.date] = record.status

    students_attendance_data = []
    for student in enrolled_students:
        student_data = {'student': student, 'attendance_by_date': {}}
        for session_date in class_session_dates:
            status = attendance_matrix[student.id].get(session_date, '') 
            student_data['attendance_by_date'][session_date] = status
        students_attendance_data.append(student_data)

    current_month_date = date(year, month, 1)
    prev_month_date = current_month_date - timedelta(days=1) 
    prev_month = {'year': prev_month_date.year, 'month': prev_month_date.month}
    
    if month == 12:
        next_month_date = date(year + 1, 1, 1)
    else:
        next_month_date = date(year, month + 1, 1)
    next_month = {'year': next_month_date.year, 'month': next_month_date.month}

    min_year_class_active = subject_class.start_date.year if subject_class.start_date else date.today().year - 2
    max_year_class_active = subject_class.end_date.year if subject_class.end_date else date.today().year + 1
    app_min_year = 2020 
    app_max_year = date.today().year + 5
    
    min_display_year = max(app_min_year, min_year_class_active)
    max_display_year = min(app_max_year, max_year_class_active)
    if max_display_year < min_display_year: 
        max_display_year = min_display_year
        
    available_years = list(range(min_display_year, max_display_year + 1))
    if not available_years: 
        available_years = list(range(date.today().year - 2, date.today().year + 2))
    if year not in available_years: 
        available_years.append(year)
        available_years.sort()

    return render_template('teacher/monthly_attendance_matrix.html',
                           subject_class=subject_class,
                           students_data=students_attendance_data,
                           class_session_dates=class_session_dates,
                           selected_year=year,
                           selected_month=month,
                           month_name=calendar.month_name[month],
                           prev_month_nav=prev_month,
                           next_month_nav=next_month,
                           available_years=available_years,
                           calendar=calendar,
                           title=f"Monthly Attendance: {subject_class.name}")
