from aiogram.fsm.state import State, StatesGroup

class RegistrationStates(StatesGroup):
    """States for user registration process"""
    name = State()
    surname = State()
    age = State()
    questions = State()  # Added for questionnaire during registration

class ApplicationStates(StatesGroup):
    """States for application process (legacy)"""
    city = State()
    timeslot = State()
    questions = State()  # This state will be used for all questions
    confirmation = State()

class EventApplicationStates(StatesGroup):
    """States for event application process"""
    event_selection = State()
    city_selection = State()
    day_selection = State()  # New state for selecting days of the week
    time_selection = State()  # New state for selecting multiple time slots
    review_selection = State()  # New state for reviewing selected slots
    questions = State()  # This state will be used for all questions
    confirmation = State()