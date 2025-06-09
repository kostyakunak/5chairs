from aiogram.fsm.state import State, StatesGroup

class RegistrationStates(StatesGroup):
    """States for user registration process"""
    name = State()
    surname = State()
    age = State()
    questions = State()  # Added for questionnaire during registration