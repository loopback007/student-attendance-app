# app/main/routes.py
from flask import render_template, request, current_app, flash, redirect, url_for # Added redirect, url_for
from flask_login import login_required, current_user 
from . import main # Import the blueprint instance
from app import db
from app.models import SubjectClass, User, Subject, ClassSchedule, Holiday # Make sure User is imported
from datetime import datetime, timedelta, time 
# Import the new profile forms
from .forms import UpdateProfileForm, ChangePasswordForm # Assuming forms.py is in the same 'main' directory

@main.route('/')
@main.route('/dashboard')
@login_required
def dashboard():
    """
    Main dashboard page.
    Renders the main dashboard template.
    """
    return render_template('main/dashboard.html', title='Dashboard')


# --- School Timetable Feature ---
# ... (get_week_dates and school_timetable functions remain here) ...
def get_week_dates(target_date):
    start_of_week = target_date - timedelta(days=target_date.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    return start_of_week, end_of_week

@main.route('/timetable')
@login_required 
def school_timetable():
    now_from_server = datetime.now()
    today_date_obj = now_from_server.date()
    current_time_hour = now_from_server.hour
    current_app.logger.info(f"TIMETABLE_VIEW: Server's datetime.now() is: {now_from_server}")
    current_app.logger.info(f"TIMETABLE_VIEW: Determined today_date_obj: {today_date_obj}")
    current_app.logger.info(f"TIMETABLE_VIEW: Determined current_time_hour: {current_time_hour}")

    date_str = request.args.get('date')
    if date_str:
        try:
            current_day_for_week = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            current_day_for_week = datetime.today().date()
            flash("Invalid date format for timetable, defaulting to current week.", "warning")
    else:
        current_day_for_week = datetime.today().date()

    start_of_week, end_of_week = get_week_dates(current_day_for_week)
    current_app.logger.debug(f"TIMETABLE_VIEW: Viewing week: {start_of_week} to {end_of_week}")

    days_of_week_display = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    time_slots = [time(h, 0) for h in range(8, 18)]
    
    schedules_query = ClassSchedule.query.join(
        SubjectClass, ClassSchedule.subject_class_id == SubjectClass.id
    ).filter(
        SubjectClass.start_date <= end_of_week,
        SubjectClass.end_date >= start_of_week
    ).options(
        db.joinedload(ClassSchedule.subject_class).joinedload(SubjectClass.subject_taught),
        db.joinedload(ClassSchedule.subject_class).joinedload(SubjectClass.teacher_user)
    ).order_by(ClassSchedule.day_of_week, ClassSchedule.start_time).all()
    current_app.logger.debug(f"TIMETABLE_VIEW: Number of schedules fetched from DB for the week: {len(schedules_query)}")

    holidays_in_week_query = Holiday.query.filter(
        Holiday.date >= start_of_week, Holiday.date <= end_of_week
    ).all()
    holiday_dates_in_week = {h.date for h in holidays_in_week_query} 
    holiday_details_map = {h.date: h for h in holidays_in_week_query} 
    current_app.logger.debug(f"TIMETABLE_VIEW: Holiday dates in week: {holiday_dates_in_week}")

    timetable_data = {day: {slot.strftime('%H:%M'): [] for slot in time_slots} for day in days_of_week_display}

    for schedule in schedules_query:
        current_app.logger.debug(f"TIMETABLE_VIEW: Processing DB schedule: ID={schedule.id}, Day='{schedule.day_of_week}', Start={schedule.start_time}, ClassID={schedule.subject_class_id}, SubjectClass Name='{schedule.subject_class.name if schedule.subject_class else 'N/A'}'")
        if schedule.day_of_week in timetable_data:
            day_slots = timetable_data[schedule.day_of_week]
            for slot_time_obj in time_slots:
                slot_hour_start = slot_time_obj
                slot_hour_end = time((slot_time_obj.hour + 1) % 24, 0) if slot_time_obj.hour < 23 else time(23, 59, 59)
                if schedule.start_time >= slot_hour_start and schedule.start_time < slot_hour_end:
                    entry_details = {
                        'id': schedule.id, 'class_id': schedule.subject_class.id, 
                        'class_name': schedule.subject_class.name,
                        'subject_name': schedule.subject_class.subject_taught.name,
                        'teacher_name': schedule.subject_class.teacher_user.first_name + " " + schedule.subject_class.teacher_user.last_name if schedule.subject_class.teacher_user else "N/A",
                        'start_time_str': schedule.start_time.strftime('%H:%M'),
                        'end_time_str': schedule.end_time.strftime('%H:%M'),
                        'location': schedule.location or "N/A", 'rowspan': 1 
                    }
                    base_date_for_calc = datetime.min.date() 
                    start_dt = datetime.combine(base_date_for_calc, schedule.start_time)
                    end_dt = datetime.combine(base_date_for_calc, schedule.end_time)
                    duration_seconds = (end_dt - start_dt).total_seconds()
                    if duration_seconds < 0: duration_seconds += 24 * 3600
                    duration_hours = duration_seconds / 3600.0
                    entry_details['rowspan'] = max(1, int(round(duration_hours)))
                    day_slots[slot_hour_start.strftime('%H:%M')].append(entry_details)
                    current_app.logger.debug(f"TIMETABLE_VIEW: Added entry to timetable: Day='{schedule.day_of_week}', Slot='{slot_hour_start.strftime('%H:%M')}', Class='{entry_details['class_name']}', Rowspan={entry_details['rowspan']}'")
                    break 
        else:
            current_app.logger.warning(f"TIMETABLE_VIEW: Schedule day '{schedule.day_of_week}' (ID: {schedule.id}) for class '{schedule.subject_class.name if schedule.subject_class else 'N/A'}' not found in display days: {days_of_week_display}. Check 'day_of_week' string in database.")

    prev_week_date = start_of_week - timedelta(days=7)
    next_week_date = start_of_week + timedelta(days=7)

    return render_template('main/timetable_view.html',
                           title=f"School Timetable - Week of {start_of_week.strftime('%b %d, %Y')}",
                           timetable_data=timetable_data,
                           days_of_week=days_of_week_display,
                           time_slots=[slot.strftime('%H:%M') for slot in time_slots],
                           start_of_week_date_obj=start_of_week, 
                           start_of_week_str=start_of_week.strftime('%Y-%m-%d'), 
                           prev_week_str=prev_week_date.strftime('%Y-%m-%d'),
                           next_week_str=next_week_date.strftime('%Y-%m-%d'),
                           current_week_label=f"{start_of_week.strftime('%b %d')} - {end_of_week.strftime('%b %d, %Y')}",
                           datetime_module=datetime,
                           timedelta_module=timedelta,
                           holiday_dates_in_week=holiday_dates_in_week,
                           holiday_details_map=holiday_details_map,
                           today_date=today_date_obj,         
                           current_hour=current_time_hour     
                           )

# --- NEW User Profile Route ---
@main.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    profile_form = UpdateProfileForm(obj=current_user) # Pre-populate with current user's data
    password_form = ChangePasswordForm()

    # Check which form was submitted by looking for the submit button's name
    if profile_form.submit_profile.data and profile_form.validate_on_submit():
        # Ensure email uniqueness if changed (handled by form's validate_email)
        current_user.email = profile_form.email.data
        current_user.first_name = profile_form.first_name.data
        current_user.last_name = profile_form.last_name.data
        try:
            db.session.commit()
            flash('Your profile has been updated successfully.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating profile: {str(e)}', 'danger')
            current_app.logger.error(f"Error updating profile for user {current_user.username}: {e}", exc_info=True)
        return redirect(url_for('main.profile')) # Redirect to refresh and clear POST

    if password_form.submit_password.data and password_form.validate_on_submit():
        # Password validation (current pass correct, new pass matches confirm) handled by form
        current_user.set_password(password_form.new_password.data)
        try:
            db.session.commit()
            flash('Your password has been changed successfully.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error changing password: {str(e)}', 'danger')
            current_app.logger.error(f"Error changing password for user {current_user.username}: {e}", exc_info=True)
        return redirect(url_for('main.profile')) # Redirect to refresh

    # For GET requests, or if form validation fails, pre-populate profile form
    if request.method == 'GET':
        profile_form.username.data = current_user.username
        profile_form.email.data = current_user.email
        profile_form.first_name.data = current_user.first_name
        profile_form.last_name.data = current_user.last_name
        
    return render_template('main/profile.html', 
                           title="My Profile", 
                           profile_form=profile_form, 
                           password_form=password_form)

