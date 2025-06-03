from aiogram.fsm.state import State, StatesGroup

class AdminAuthStates(StatesGroup):
    """States for admin authentication"""
    waiting_for_auth = State()

class CityManagementStates(StatesGroup):
    """States for city management"""
    add_city = State()
    edit_city = State()
    select_city_to_edit = State()
    confirm_delete = State()

class TimeslotManagementStates(StatesGroup):
    """States for time slot management"""
    add_city = State()
    add_day = State()
    add_start_time = State()
    add_end_time = State()
    select_timeslot_to_edit = State()
    edit_day = State()
    edit_start_time = State()
    edit_end_time = State()
    confirm_delete = State()
    activate_deactivate = State()
    select_city_for_toggle = State()

class QuestionManagementStates(StatesGroup):
    """States for question management"""
    add_question = State()
    add_order = State()
    select_question_to_edit = State()
    edit_question = State()
    edit_order = State()
    confirm_delete = State()
    reorder_questions = State()

class ApplicationReviewStates(StatesGroup):
    """States for application review"""
    select_application = State()
    review_application = State()
    add_notes = State()
    confirm_decision = State()
    add_to_meeting = State()
    batch_review = State()
    filter_by_time = State()
    assign_to_meeting = State()
    view_compatible_meetings = State()
    choose_meeting_date = State()
    enter_meeting_name = State()
    choose_venue = State()
    enter_venue_manually = State()
    enter_venue_address = State()
    confirm_meeting_creation = State()
    select_user_for_meeting = State()
    enter_admin_note = State()

class MeetingManagementStates(StatesGroup):
    """States for meeting management"""
    create_name = State()
    create_date = State()
    create_time = State()
    create_city = State()
    create_venue = State()
    select_meeting = State()
    select_meeting_to_manage = State()
    add_members = State()
    select_user = State()
    remove_members = State()
    confirm_meeting = State()
    confirm_low_attendance = State()  # New state for confirming meetings with low attendance
    cancel_meeting = State()
    select_available_date = State()
    select_time_preference = State()
    match_users = State()
    view_suggested_users = State()
    filter_users_by_preference = State()
    edit_meeting_field = State()
    edit_meeting_date = State()
    edit_meeting_time = State()
    smart_meeting_date = State()
    smart_meeting_timeslot = State()
    smart_meeting_venue = State()
    smart_meeting_venue_manual = State()
    smart_select_users = State()
    smart_view_user = State()
    smart_confirm_creation = State()

class VenueManagementStates(StatesGroup):
    """States for venue management"""
    select_city = State()
    enter_name = State()
    enter_address = State()
    enter_description = State()
    confirm_venue = State()
    select_venue_to_edit = State()
    edit_venue = State()
    edit_address = State()
    confirm_delete = State()