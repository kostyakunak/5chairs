from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.db import add_user, get_user

# Define states for registration process
class RegistrationStates(StatesGroup):
    name = State()
    age = State()
    city = State()
    description = State()

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
            f"Use /profile to view your profile or /join to join a meeting."
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

# Name handler
@router.message(RegistrationStates.name)
async def process_name(message: Message, state: FSMContext):
    # Save name to state
    await state.update_data(name=message.text)
    
    # Ask for age
    await message.answer("Great! Now, how old are you? (Please enter a number)")
    
    # Set state to wait for age
    await state.set_state(RegistrationStates.age)

# Age handler
@router.message(RegistrationStates.age)
async def process_age(message: Message, state: FSMContext):
    # Validate age
    if not message.text.isdigit():
        await message.answer("Please enter a valid number for your age.")
        return
    
    age = int(message.text)
    if age < 18 or age > 100:
        await message.answer("Please enter a valid age between 18 and 100.")
        return
    
    # Save age to state
    await state.update_data(age=age)
    
    # Ask for city
    await message.answer("Which city do you live in?")
    
    # Set state to wait for city
    await state.set_state(RegistrationStates.city)

# City handler
@router.message(RegistrationStates.city)
async def process_city(message: Message, state: FSMContext):
    # Save city to state
    await state.update_data(city=message.text)
    
    # Ask for description
    await message.answer(
        "Almost done! Please provide a brief description about yourself.\n"
        "This will help others get to know you better."
    )
    
    # Set state to wait for description
    await state.set_state(RegistrationStates.description)

# Description handler
@router.message(RegistrationStates.description)
async def process_description(message: Message, state: FSMContext):
    # Save description to state
    await state.update_data(description=message.text)
    
    # Get all registration data
    data = await state.get_data()
    
    # Save user to database
    user_id = message.from_user.id
    username = message.from_user.username
    await add_user(
        user_id=user_id,
        username=username,
        name=data['name'],
        city=data['city'],
        age=data['age'],
        description=data['description']
    )
    
    # Create keyboard with commands
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="/profile"), KeyboardButton(text="/join")]
        ],
        resize_keyboard=True
    )
    
    # Finish registration
    await message.answer(
        f"Registration complete! Welcome to 5 Chairs, {data['name']}!\n\n"
        f"You can use /profile to view your profile or /join to join a meeting.",
        reply_markup=keyboard
    )
    
    # Clear state
    await state.clear()

# Function to register handlers with the dispatcher
def register_start_handlers(dp):
    dp.include_router(router)
