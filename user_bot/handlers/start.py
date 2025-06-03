import logging
from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Set up logger
logger = logging.getLogger(__name__)

from database.db import add_user, get_user, get_active_questions, add_user_answer
from user_bot.states import RegistrationStates

# Create router
router = Router()

# Start command handler
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Check if user already exists
    user = await get_user(user_id)
    
    if user:
        await message.answer(
            f"Welcome back, {user['name']}! You are already registered.\n"
            f"Use the Apply button to browse and apply for available events."
        )
        return
    
    # Start registration process
    await message.answer(
        "Welcome to 5 Chairs! 🪑🪑🪑🪑🪑\n\n"
        "This bot helps you find and join meetups with like-minded people.\n\n"
        "Let's start with your registration. What's your name?"
    )
    
    # Set state to wait for name
    await state.set_state(RegistrationStates.name)

# Cancel command handler for registration
@router.message(Command("cancel"))
async def cmd_cancel_registration(message: Message, state: FSMContext):
    # Get current state
    current_state = await state.get_state()
    
    # Check if user is in registration process
    if current_state in [RegistrationStates.name, RegistrationStates.surname, RegistrationStates.age]:
        await message.answer(
            "Registration cancelled. You can start again with /start when you're ready."
        )
        # Clear state
        await state.clear()
    else:
        await message.answer(
            "You're not in the registration process. Use /help to see available commands."
        )

# Name handler
@router.message(RegistrationStates.name)
async def process_name(message: Message, state: FSMContext):
    # Check for cancel command
    if message.text.lower() == "cancel":
        await message.answer(
            "Registration cancelled. You can start again with /start when you're ready."
        )
        # Clear state
        await state.clear()
        return
    
    # Save name to state
    await state.update_data(name=message.text)
    
    # Ask for surname
    await message.answer(
        "Great! Now, what's your surname?\n\n"
        "You can type 'cancel' at any time to cancel registration."
    )
    
    # Set state to wait for surname
    await state.set_state(RegistrationStates.surname)

# Surname handler
@router.message(RegistrationStates.surname)
async def process_surname(message: Message, state: FSMContext):
    # Check for cancel command
    if message.text.lower() == "cancel":
        await message.answer(
            "Registration cancelled. You can start again with /start when you're ready."
        )
        # Clear state
        await state.clear()
        return
    
    # Save surname to state
    await state.update_data(surname=message.text)
    
    # Ask for age
    await message.answer(
        "Now, how old are you? (Please enter a number between 18 and 100)\n\n"
        "You can type 'cancel' at any time to cancel registration."
    )
    
    # Set state to wait for age
    await state.set_state(RegistrationStates.age)

# Age handler
@router.message(RegistrationStates.age)
async def process_age(message: Message, state: FSMContext):
    # Check for cancel command
    if message.text.lower() == "cancel":
        await message.answer(
            "Registration cancelled. You can start again with /start when you're ready."
        )
        # Clear state
        await state.clear()
        return
    
    # Validate age
    if not message.text.isdigit():
        await message.answer(
            "Please enter a valid number for your age.\n"
            "You can type 'cancel' to cancel registration."
        )
        return
    
    age = int(message.text)
    if age < 18 or age > 100:
        await message.answer(
            "Please enter a valid age between 18 and 100.\n"
            "You can type 'cancel' to cancel registration."
        )
        return
    
    # Save age to state
    await state.update_data(age=age)
    
    # Create user record in database BEFORE asking questions
    user_id = message.from_user.id
    username = message.from_user.username
    data = await state.get_data()
    
    try:
        # Save user to database first to avoid foreign key violations
        await add_user(
            user_id=user_id,
            username=username,
            name=data['name'],
            surname=data['surname'],
            age=data['age']
        )
        logger.info(f"User {user_id} registered successfully before answering questions")
    except Exception as e:
        # Log the error
        logger.error(f"Failed to register user {user_id} before questions: {e}")
        
        # Inform the user
        await message.answer(
            "Sorry, there was an error during registration. Please try again later or contact support."
        )
        
        # Clear state
        await state.clear()
        return
    
    # Get questions for registration
    questions = await get_active_questions()
    
    if not questions:
        # If no questions, complete registration without questions
        await complete_final_steps(message, state)
        return
    
    # Save questions to state
    await state.update_data(
        questions=[(q['id'], q['text']) for q in questions],
        current_question_index=0
    )
    
    # Get first question
    data = await state.get_data()
    question_id, question_text = data['questions'][0]
    
    await message.answer(
        "Great! Now, please answer a few questions to help us match you with like-minded people.\n\n"
        f"Question 1/{len(data['questions'])}:\n{question_text}"
    )
    
    # Set state to wait for question answers
    await state.set_state(RegistrationStates.questions)

# Questions handler
@router.message(RegistrationStates.questions)
async def process_question_answer(message: Message, state: FSMContext):
    # Check for cancel command
    if message.text.lower() == "cancel":
        await message.answer(
            "Registration cancelled. You can start again with /start when you're ready."
        )
        # Clear state
        await state.clear()
        return
    
    # Get current state data
    data = await state.get_data()
    current_index = data['current_question_index']
    questions = data['questions']
    
    # Save answer to current question
    question_id, _ = questions[current_index]
    user_id = message.from_user.id
    
    try:
        await add_user_answer(user_id, question_id, message.text)
    except Exception as e:
        logger.error(f"Failed to save answer for user {user_id}: {e}")
        # Add more detailed error logging to help diagnose issues
        if "violates foreign key constraint" in str(e):
            logger.error(f"Foreign key violation when saving answer. User {user_id} might not exist in the database.")
        await message.answer(
            "Sorry, there was an error saving your answer. Please try again."
        )
        return
    
    # Move to next question or finish
    current_index += 1
    
    if current_index < len(questions):
        # Update current question index
        await state.update_data(current_question_index=current_index)
        
        # Get next question
        question_id, question_text = questions[current_index]
        
        await message.answer(
            f"Question {current_index + 1}/{len(questions)}:\n{question_text}"
        )
    else:
        # All questions answered, complete the final steps of registration
        await complete_final_steps(message, state)

# Helper function to complete final steps of registration
async def complete_final_steps(message: Message, state: FSMContext):
    # Get all registration data
    data = await state.get_data()
    user_id = message.from_user.id
    
    # Create keyboard with commands
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Apply")],
            [KeyboardButton(text="My meetings")]
        ],
        resize_keyboard=True
    )
    
    # Finish registration
    await message.answer(
        f"Registration complete! Welcome to 5 Chairs, {data['name']}!\n\n"
        f"Tap 'Apply' to select a date and time for your activity. "
        f"Use /applications to view your submitted applications.",
        reply_markup=keyboard
    )
    
    # Clear state
    await state.clear()

# Help command handler
@router.message(Command("help"))
async def cmd_help(message: Message):
    logger.info(f"User {message.from_user.id} requested help")
    await message.answer(
        "5 Chairs Bot Commands:\n\n"
        "/start - Start the bot and register\n"
        "/cancel - Cancel the registration process\n"
        "/menu - Show the main menu\n"
        "Apply - Select a date and time for your activity and submit your application\n"
        "/applications - View all your applications\n"
        "/help - Show this help message\n\n"
        "DEPRECATED COMMANDS:\n"
        "/activities, /events, /meetings - These have been replaced by the 'Apply' button for a simpler experience.\n"
        "/apply - Old application system\n"
        "/status - Old status check\n\n"
        "You can also use the menu buttons for quick access to these features."
    )

# Menu command handler
@router.message(Command("menu"))
async def cmd_menu(message: Message):
    # Create keyboard with commands
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Apply")],
            [KeyboardButton(text="My meetings")]
        ],
        resize_keyboard=True
    )
    
    logger.info(f"User {message.from_user.id} requested main menu")
    
    await message.answer(
        "Main Menu\n\n"
        "• Apply - Select a date and time for your activity\n"
        "• /applications - View all your applications\n"
        "• /help - Show help message\n",
        reply_markup=keyboard
    )

# Function to register handlers with the dispatcher
def register_start_handlers(dp):
    logger.info("Registering start handlers")
    dp.include_router(router)