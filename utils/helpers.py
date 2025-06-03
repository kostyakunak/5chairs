import logging
from datetime import datetime, date, time, timedelta

logger = logging.getLogger(__name__)

def format_date(date_obj, format_str="%d.%m.%Y", include_day_name=False):
    """
    Format a date object to a human-readable string
    
    Args:
        date_obj: The date object to format
        format_str: The format string to use (default: "%d.%m.%Y")
        include_day_name: Whether to include the day name (default: False)
    
    Returns:
        A formatted date string
    """
    if not date_obj:
        return "N/A"
    
    try:
        if include_day_name:
            day_name = date_obj.strftime("%A")
            formatted_date = date_obj.strftime(format_str)
            return f"{day_name}, {formatted_date}"
        else:
            return date_obj.strftime(format_str)
    except Exception as e:
        logger.error(f"Error formatting date: {e}")
        return str(date_obj)

def format_time(time_obj, format_str="%H:%M"):
    """
    Format a time object to a human-readable string
    
    Args:
        time_obj: The time object to format
        format_str: The format string to use (default: "%H:%M")
    
    Returns:
        A formatted time string
    """
    if not time_obj:
        return "N/A"
    
    try:
        return time_obj.strftime(format_str)
    except Exception as e:
        logger.error(f"Error formatting time: {e}")
        return str(time_obj)

def parse_date(date_str):
    """
    Parse a date string into a date object
    
    Supports multiple formats:
    - DD.MM.YYYY
    - YYYY-MM-DD
    - DD/MM/YYYY
    
    Args:
        date_str: The date string to parse
    
    Returns:
        A date object or None if parsing fails
    """
    formats = ["%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    
    logger.error(f"Failed to parse date: {date_str}")
    return None

def parse_time(time_str):
    """
    Parse a time string into a time object
    
    Supports multiple formats:
    - HH:MM
    - HH.MM
    - HH:MM:SS
    
    Args:
        time_str: The time string to parse
    
    Returns:
        A time object or None if parsing fails
    """
    formats = ["%H:%M", "%H.%M", "%H:%M:%S"]
    
    for fmt in formats:
        try:
            return datetime.strptime(time_str, fmt).time()
        except ValueError:
            continue
    
    logger.error(f"Failed to parse time: {time_str}")
    return None

def calculate_next_weekend():
    """Calculate the date of the next weekend (Saturday)"""
    today = date.today()
    days_until_saturday = (5 - today.weekday()) % 7
    if days_until_saturday == 0:
        days_until_saturday = 7  # If today is Saturday, schedule for next Saturday
    
    return today + timedelta(days=days_until_saturday)

def is_valid_age(age_str):
    """Validate if the provided string is a valid age"""
    if not age_str.isdigit():
        return False
    
    age = int(age_str)
    return 18 <= age <= 100

def is_valid_name(name):
    """Validate if the provided string is a valid name"""
    if not name or len(name) < 2 or len(name) > 50:
        return False
    
    # Additional validation could be added here
    return True

def is_valid_city(city):
    """Validate if the provided string is a valid city name"""
    if not city or len(city) < 2 or len(city) > 50:
        return False
    
    # Additional validation could be added here
    return True

def is_valid_description(description):
    """Validate if the provided string is a valid description"""
    if not description or len(description) > 500:
        return False
    
    # Additional validation could be added here
    return True

def get_meeting_status_emoji(status):
    """Get an emoji representing the meeting status"""
    status_emojis = {
        'pending': '⏳',
        'confirmed': '✅',
        'cancelled': '❌',
        'completed': '🎉'
    }
    
    return status_emojis.get(status.lower(), '❓')

def format_meeting_info(meeting, participant_count=None, total_needed=None):
    """Format meeting information for display"""
    status_emoji = get_meeting_status_emoji(meeting['status'])
    
    info = (
        f"{status_emoji} Meeting in {meeting['location']}\n"
        f"📅 Date: {format_date(meeting['date'])}\n"
        f"🕕 Time: {format_time(meeting['time'])}\n"
    )
    
    if participant_count is not None and total_needed is not None:
        info += f"👥 Participants: {participant_count}/{total_needed}\n"
    
    return info

def format_profile_info(user):
    """Format user profile information for display"""
    if not user:
        return "Profile not found"
    
    info = (
        f"📋 Profile Information:\n\n"
        f"👤 Name: {user['name']}\n"
    )
    
    if user.get('age'):
        info += f"🎂 Age: {user['age']}\n"
    
    if user.get('city'):
        info += f"🏙️ City: {user['city']}\n"
    
    if user.get('description'):
        info += f"📝 About: {user['description']}\n"
    
    if user.get('registration_date'):
        info += f"📅 Registered: {format_date(user['registration_date'])}\n"
    
    return info