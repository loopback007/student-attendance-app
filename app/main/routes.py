# app/main/routes.py
from flask import render_template, request, current_app, flash
from flask_login import login_required, current_user 
from . import main # Import the blueprint instance
from app import db
from app.models import SubjectClass, User, Subject, ClassSchedule 
from datetime import datetime, timedelta, time 

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

# Helper to get start and end of the week for a given date
def get_week_dates(target_date):
    """
    Returns the start (Monday) and end (Sunday) dates of the week for a given target_date.
    """
    start_of_week = target_date - timedelta(days=target_date.weekday()) # Monday
    end_of_week = start_of_week + timedelta(days=6) # Sunday
    return start_of_week, end_of_week

@main.route('/timetable')
@login_required 
def school_timetable():
    # Determine the week to display
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
    # Using current_app.logger.debug for more control via app's log level
    current_app.logger.debug(f"TIMETABLE_VIEW: Viewing week: {start_of_week} to {end_of_week}")


    # Define days of the week for display.
    # IMPORTANT: These strings MUST EXACTLY MATCH the values stored in ClassSchedule.day_of_week
    days_of_week_display = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    
    time_slots = []
    for hour in range(8, 18): # 8 AM (08:00) to 5 PM (17:00), slots are 1 hour long
        time_slots.append(time(hour, 0))
    
    # Fetch all ClassSchedule entries.
    # Filter by SubjectClass start_date and end_date to only include relevant classes for the week.
    schedules_query = ClassSchedule.query.join(
        SubjectClass, ClassSchedule.subject_class_id == SubjectClass.id
    ).filter(
        SubjectClass.start_date <= end_of_week, # Class must have started by end of week
        SubjectClass.end_date >= start_of_week   # Class must not have ended before start of week
    ).options(
        db.joinedload(ClassSchedule.subject_class).joinedload(SubjectClass.subject_taught),
        db.joinedload(ClassSchedule.subject_class).joinedload(SubjectClass.teacher_user)
    ).order_by(ClassSchedule.day_of_week, ClassSchedule.start_time).all()

    current_app.logger.debug(f"TIMETABLE_VIEW: Number of schedules fetched from DB for the week: {len(schedules_query)}")

    # Initialize timetable_data structure
    timetable_data = {day: {slot.strftime('%H:%M'): [] for slot in time_slots} for day in days_of_week_display}

    for schedule in schedules_query:
        current_app.logger.debug(f"TIMETABLE_VIEW: Processing DB schedule: ID={schedule.id}, Day='{schedule.day_of_week}', Start={schedule.start_time}, ClassID={schedule.subject_class_id}, SubjectClass Name='{schedule.subject_class.name if schedule.subject_class else 'N/A'}'")
        
        # Ensure the schedule's day_of_week from DB matches one of our display columns
        if schedule.day_of_week in timetable_data:
            day_slots = timetable_data[schedule.day_of_week]
            for slot_time_obj in time_slots:
                slot_hour_start = slot_time_obj
                # Assuming 1-hour slots, the slot ends at the beginning of the next hour
                slot_hour_end = time((slot_time_obj.hour + 1) % 24, 0) if slot_time_obj.hour < 23 else time(23, 59, 59)
                
                # Check if the class schedule's start time falls within the current 1-hour slot
                if schedule.start_time >= slot_hour_start and schedule.start_time < slot_hour_end:
                    entry_details = {
                        'id': schedule.id, # ClassSchedule ID
                        'class_id': schedule.subject_class.id, # SubjectClass ID
                        'class_name': schedule.subject_class.name,
                        'subject_name': schedule.subject_class.subject_taught.name,
                        'teacher_name': schedule.subject_class.teacher_user.first_name + " " + schedule.subject_class.teacher_user.last_name if schedule.subject_class.teacher_user else "N/A",
                        'start_time_str': schedule.start_time.strftime('%H:%M'),
                        'end_time_str': schedule.end_time.strftime('%H:%M'),
                        'location': schedule.location or "N/A",
                        'rowspan': 1 # Default, will be calculated more accurately if needed by template
                    }
                    # Calculate rowspan based on duration and slot size
                    # Combine with a date part for timedelta calculations, as time objects don't directly support subtraction for duration across midnight
                    base_date = datetime.min.date() # A common arbitrary date
                    start_dt = datetime.combine(base_date, schedule.start_time)
                    end_dt = datetime.combine(base_date, schedule.end_time)
                    
                    duration_seconds = (end_dt - start_dt).total_seconds()
                    # Handle cases where end_time is past midnight relative to start_time (e.g. 23:00 - 01:00 the next day)
                    # This simple duration calculation assumes start and end are on the same conceptual day for the schedule entry.
                    # If a class truly spans midnight into the next calendar day, this duration logic would need adjustment.
                    if duration_seconds < 0: 
                        duration_seconds += 24 * 3600 # Add a day's worth of seconds
                        
                    duration_hours = duration_seconds / 3600.0
                    entry_details['rowspan'] = max(1, int(round(duration_hours))) # Assumes 1-hour slots for rowspan calc

                    day_slots[slot_hour_start.strftime('%H:%M')].append(entry_details)
                    current_app.logger.debug(f"TIMETABLE_VIEW: Added entry to timetable: Day='{schedule.day_of_week}', Slot='{slot_hour_start.strftime('%H:%M')}', Class='{entry_details['class_name']}', Rowspan={entry_details['rowspan']}'")
                    break # Class placed in its starting slot, move to next schedule from DB
        else:
            current_app.logger.warning(f"TIMETABLE_VIEW: Schedule day '{schedule.day_of_week}' (ID: {schedule.id}) for class '{schedule.subject_class.name if schedule.subject_class else 'N/A'}' not found in display days: {days_of_week_display}. Check 'day_of_week' string in database.")


    # Navigation links
    prev_week_date = start_of_week - timedelta(days=7)
    next_week_date = start_of_week + timedelta(days=7)

    return render_template('main/timetable_view.html', # Ensure this template exists
                           title=f"School Timetable - Week of {start_of_week.strftime('%b %d, %Y')}",
                           timetable_data=timetable_data,
                           days_of_week=days_of_week_display,
                           time_slots=[slot.strftime('%H:%M') for slot in time_slots],
                           start_of_week_str=start_of_week.strftime('%Y-%m-%d'), # For date picker default
                           prev_week_str=prev_week_date.strftime('%Y-%m-%d'),
                           next_week_str=next_week_date.strftime('%Y-%m-%d'),
                           current_week_label=f"{start_of_week.strftime('%b %d')} - {end_of_week.strftime('%b %d, %Y')}",
                           datetime=datetime,  # For use in template if needed
                           timedelta=timedelta # For use in template if needed
                           )
