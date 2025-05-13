# app/teacher/routes.py
from flask import render_template, request, redirect, url_for, flash, abort, current_app
from flask_login import login_required, current_user
from . import teacher 
from app.decorators import teacher_required 
# MODIFIED: Import Holiday model
from app.models import User, SubjectClass, Student, Attendance, Holiday 
from app.teacher.forms import MarkAttendanceForm, StudentAttendanceEntryForm 
from app import db
# MODIFIED: Ensure 'date' and 'timedelta' are available from datetime
from datetime import date, datetime, timedelta 
from collections import defaultdict
import calendar # For month iteration

@teacher.route('/')
@login_required
@teacher_required
def teacher_dashboard():
    # This route currently redirects to my_classes.
    # If you want a dedicated dashboard page, you'd render a template here.
    # For now, we'll add holiday info to the 'my_classes' view.
    return redirect(url_for('teacher.my_classes'))

@teacher.route('/my-classes')
@login_required
@teacher_required
def my_classes():
    assigned_classes = current_user.classes_taught.options(
        db.joinedload(SubjectClass.subject_taught)
    ).order_by(SubjectClass.name).all()
    
    # --- ADDED LOGIC TO FETCH UPCOMING HOLIDAYS ---
    today = date.today()
    # Fetch holidays from today for the next (e.g.) 60 days, limit to a few
    # Using PyDate.today() for consistency if you aliased `date` in models.py
    # but here `date.today()` is fine as `date` is directly from `datetime`.
    upcoming_holidays_query = Holiday.query.filter(Holiday.date >= today).order_by(Holiday.date.asc())
    
    # Optional: Limit the number of holidays shown, e.g., next 3-5
    upcoming_holidays = upcoming_holidays_query.limit(5).all() 
    
    # Optional: You might want to fetch for a specific period, e.g., next 60 days
    # end_date_for_holidays = today + timedelta(days=60)
    # upcoming_holidays_strict_period = Holiday.query.filter(
    # Holiday.date >= today,
    # Holiday.date <= end_date_for_holidays
    # ).order_by(Holiday.date.asc()).all()
    # --- END OF ADDED LOGIC ---
    
    return render_template('teacher/my_classes.html', 
                           classes=assigned_classes, 
                           upcoming_holidays=upcoming_holidays, # Pass holidays to template
                           title="My Classes & Dashboard") # Title can reflect it's a dashboard
                           
@teacher.route('/holidays')
@login_required
@teacher_required # Or a more general permission decorator if needed
def view_all_holidays():
    # Get the current year, or allow year selection via query parameter
    year = request.args.get('year', default=date.today().year, type=int)
    
    # Fetch holidays for the selected year, ordered by date
    holidays_for_year = Holiday.query.filter(
        db.extract('year', Holiday.date) == year
    ).order_by(Holiday.date.asc()).all()
    
    # Get a list of years for which holidays are configured, for a year selector dropdown
    available_years_query = db.session.query(db.extract('year', Holiday.date).label('year')).distinct().order_by(db.desc('year'))
    available_years = [y.year for y in available_years_query.all()]

    if not available_years and not holidays_for_year : # If no holidays at all in DB
        available_years = [date.today().year] # Default to current year if no holidays exist
    elif year not in available_years and available_years: # If selected year has no holidays but other years do
         if date.today().year in available_years: # Try current year if available
            year = date.today().year
         else: # Else just pick the latest available year
            year = available_years[0] if available_years else date.today().year
         # Re-fetch for the adjusted year
         holidays_for_year = Holiday.query.filter(
            db.extract('year', Holiday.date) == year
         ).order_by(Holiday.date.asc()).all()


    return render_template('teacher/all_holidays.html', 
                           holidays=holidays_for_year, 
                           selected_year=year,
                           available_years=available_years,
                           title=f"School Holidays & Events for {year}")

# Helper function to parse day of week from schedule string
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
def mark_attendance(class_id): # class_id here is subject_class.id
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

    # Determine default/selected date for attendance
    default_class_date_for_week = today
    if scheduled_weekday is not None:
        days_difference = scheduled_weekday - today.weekday()
        default_class_date_for_week = today + timedelta(days=days_difference)

    selected_date_str = request.args.get('attendance_date')
    if selected_date_str:
        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
            if scheduled_weekday is not None and selected_date.weekday() != scheduled_weekday:
                flash(f"Attendance for this class is typically on {subject_class.schedule_details[:3]}. Selected date is not a scheduled class day. Showing default date instead.", "warning")
                selected_date = default_class_date_for_week
        except ValueError:
            flash("Invalid date format. Showing default date.", "warning")
            selected_date = default_class_date_for_week
    else:
        if request.method == 'POST' and form.attendance_date.data:
             selected_date = form.attendance_date.data
        else:
            selected_date = default_class_date_for_week
    
    form.attendance_date.data = selected_date # Set form's date for display
    # --- ADDED/UPDATED: Check if selected_date is a holiday ---
    holiday_on_selected_date = None
    if selected_date: # Ensure selected_date is valid before querying
        holiday_on_selected_date = Holiday.query.filter_by(date=selected_date).first()

    if request.method == 'POST' and form.validate_on_submit():
        # Ensure selected date for submission matches the one used for form population if it changed
        selected_date = form.attendance_date.data

        if scheduled_weekday is not None and selected_date.weekday() != scheduled_weekday:
            flash(f"Submission error: Attendance for this class should be on a {subject_class.schedule_details[:3]}. Please select a valid date.", "danger")
        else:
            try:
                for student_entry_data in form.students_attendance.data:
                    student_id = student_entry_data['student_id']
                    status_val = student_entry_data['status'] # This is already a string e.g., 'present'
                    remarks = student_entry_data['remarks']
                    
                    # Use new field names: subject_class_id and date
                    attendance_record = Attendance.query.filter_by(
                        student_id=student_id, 
                        subject_class_id=class_id, # Use class_id (which is subject_class.id)
                        date=selected_date
                    ).first()
                    
                    if attendance_record:
                        attendance_record.status = status_val # Assign string directly
                        attendance_record.remarks = remarks
                        attendance_record.recorded_by_user_id = current_user.id
                        # 'updated_at' will be auto-updated by the model
                    else:
                        attendance_record = Attendance(
                            student_id=student_id, 
                            subject_class_id=class_id, # Use class_id
                            date=selected_date, 
                            status=status_val, # Assign string directly
                            remarks=remarks, 
                            recorded_by_user_id=current_user.id
                            # 'created_at' will be set by default by the model
                        )
                        db.session.add(attendance_record)
                db.session.commit()
                flash(f'Attendance for {selected_date.strftime("%A, %B %d, %Y")} saved successfully!', 'success')
                return redirect(url_for('teacher.mark_attendance', class_id=class_id, attendance_date=selected_date.strftime('%Y-%m-%d')))
            except Exception as e:
                db.session.rollback()
                flash(f'Error saving attendance: {str(e)}', 'danger')
                current_app.logger.error(f"Error in mark_attendance POST: {e}", exc_info=True) # Added logger

    # Populate form for GET request or if POST validation failed
    # Clear previous entries if any (important for FieldList)
    while len(form.students_attendance) > 0:
        form.students_attendance.pop_entry()

    enrolled_students = subject_class.students_enrolled.filter(Student.is_active==True).order_by(Student.last_name, Student.first_name).all()
    for student in enrolled_students:
        # Use new field names: subject_class_id and date
        existing_attendance = Attendance.query.filter_by(
            student_id=student.id, 
            subject_class_id=class_id, # Use class_id
            date=selected_date
        ).first()
        
        student_form_entry = StudentAttendanceEntryForm() # This form's status field expects a string
        student_form_entry.student_id = student.id
        
        if existing_attendance:
            student_form_entry.status = existing_attendance.status # status is already a string
            student_form_entry.remarks = existing_attendance.remarks
        else:
            student_form_entry.status = 'present' # Default to string 'present'
        form.students_attendance.append_entry(student_form_entry)
        
    return render_template('teacher/mark_attendance.html', 
                           form=form, 
                           subject_class=subject_class, 
                           title=f"Mark Attendance for {subject_class.name}",
                           selected_date_for_display=selected_date, 
                           enrolled_students_for_template=enrolled_students, # Pass students for display in template
                           scheduled_weekday_num=scheduled_weekday,
                           holiday_info=holiday_on_selected_date) # Pass holiday_info


@teacher.route('/class/<int:class_id>/attendance-report')
@login_required
@teacher_required
def class_attendance_report(class_id): # class_id here is subject_class.id
    subject_class = SubjectClass.query.options(
        db.joinedload(SubjectClass.subject_taught),
        db.joinedload(SubjectClass.teacher_user)
    ).get_or_404(class_id)

    if not current_user.is_admin and not current_user.is_staff and subject_class.teacher_user_id != current_user.id :
        flash("You are not authorized to view the report for this class.", "danger")
        return redirect(url_for('teacher.my_classes'))

    enrolled_students = subject_class.students_enrolled.filter(Student.is_active==True).order_by(Student.last_name, Student.first_name).all()
    
    # Use new field name: subject_class_id
    all_attendance_records = Attendance.query.filter_by(subject_class_id=class_id).all()

    student_summary_data = {}
    for student in enrolled_students:
        student_summary_data[student.id] = {
            'student_obj': student,
            'total_present': 0, 'total_absent': 0, 'total_late': 0, 'total_excused': 0,
            'total_public_holiday': 0, 'total_school_holiday': 0, # For new statuses
            'total_sessions_recorded': 0
        }

    # Use new field name: date
    unique_class_session_dates = db.session.query(Attendance.date).filter_by(subject_class_id=class_id).distinct().count()

    for record in all_attendance_records:
        if record.student_id in student_summary_data:
            summary = student_summary_data[record.student_id]
            summary['total_sessions_recorded'] += 1
            
            # Use string comparisons for status
            if record.status == 'present':
                summary['total_present'] += 1
            elif record.status == 'absent':
                summary['total_absent'] += 1
            elif record.status == 'late':
                summary['total_late'] += 1
            elif record.status == 'excused':
                summary['total_excused'] += 1
            elif record.status == 'public_holiday': # Handle new status
                summary['total_public_holiday'] += 1
            elif record.status == 'school_holiday': # Handle new status
                summary['total_school_holiday'] += 1
    
    return render_template('teacher/class_attendance_report.html',
                           subject_class=subject_class,
                           student_summary_data=student_summary_data.values(),
                           unique_class_session_dates=unique_class_session_dates,
                           title=f"Attendance Report for {subject_class.name}")
                           
def get_scheduled_class_dates_for_month(subject_class, year, month):
    """
    Helper function to get all actual dates a class is scheduled for in a given month and year.
    """
    scheduled_dates = []
    if not subject_class.schedule_details:
        return scheduled_dates

    day_map_str_to_int = {
        'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6
    }
    scheduled_weekdays = []
    details_lower = subject_class.schedule_details.lower()
    for day_str, day_int in day_map_str_to_int.items():
        if day_str in details_lower:
            scheduled_weekdays.append(day_int)
    
    if not scheduled_weekdays:
        single_scheduled_day = parse_scheduled_day(subject_class.schedule_details)
        if single_scheduled_day is not None:
            scheduled_weekdays.append(single_scheduled_day)

    if not scheduled_weekdays:
        current_app.logger.warning(f"Could not determine scheduled weekdays for class {subject_class.id} from '{subject_class.schedule_details}'")
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
@login_required # Keep @login_required
# REMOVED @teacher_required decorator from here to allow internal check to handle roles
def monthly_class_attendance_matrix(class_id):
    subject_class = SubjectClass.query.options(
        db.joinedload(SubjectClass.subject_taught),
        db.joinedload(SubjectClass.teacher_user)
    ).get_or_404(class_id)

    # This internal authorization check allows admin, staff, or the assigned teacher
    if not (current_user.is_authenticated and 
            (current_user.is_admin or \
             current_user.is_staff or \
             (current_user.is_teacher and subject_class.teacher_user_id == current_user.id))):
        flash("You are not authorized to view this attendance matrix.", "danger")
        # Redirect to a more general page if not the teacher of this specific class,
        # or if a non-admin/staff/teacher tries to access.
        # If it's a teacher but not THEIR class, teacher.my_classes is fine.
        # If it's another role without rights, main.dashboard or login might be better.
        if current_user.is_teacher:
            return redirect(url_for('teacher.my_classes'))
        else: # For other roles that might be logged in but not admin/staff
            return redirect(url_for('main.dashboard')) # Or appropriate general access page

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
        Attendance.student_id.in_([s.id for s in enrolled_students] if enrolled_students else []), # Handle empty student list
        Attendance.date.in_(class_session_dates) if class_session_dates else [] # Handle empty session dates
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

    # Determine available years for the dropdown
    # This could be a fixed range or based on actual data
    min_year_class_active = subject_class.start_date.year if subject_class.start_date else date.today().year - 2
    max_year_class_active = subject_class.end_date.year if subject_class.end_date else date.today().year + 1
    # Ensure the selected year is within a reasonable overall range for the app
    app_min_year = 2020 
    app_max_year = date.today().year + 5
    
    min_display_year = max(app_min_year, min_year_class_active)
    max_display_year = min(app_max_year, max_year_class_active)
    if max_display_year < min_display_year: # Handle edge case where class dates are outside app range
        max_display_year = min_display_year
        
    available_years = list(range(min_display_year, max_display_year + 1))
    if not available_years: # Fallback
        available_years = list(range(date.today().year - 2, date.today().year + 2))
    if year not in available_years: # Ensure selected year is an option
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