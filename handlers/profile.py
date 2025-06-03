from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.db import get_user, update_user, get_user_meetings

# Define states for profile editing
class ProfileEditStates(StatesGroup):
    menu = State()
    name = State()
    age = State()
    city = State()
    description = State()

# Create router
router = Router()

# Profile command handler
@router.message(Command("profile"))
async def cmd_profile(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Get user from database
    user = await get_user(user_id)
    
    if not user:
        await message.answer(
            "You are not registered yet. Please use /start to register."
        )
        return
    
    # Get user's meetings
    meetings = await get_user_meetings(user_id)
    
    # Format meetings info
    meetings_info = ""
    if meetings:
        meetings_info = "\n\nYour upcoming meetings:\n"
        for meeting in meetings:
            meetings_info += f"- {meeting['date'].strftime('%d.%m.%Y')} at {meeting['time'].strftime('%H:%M')} in {meeting['location']}\n"
    else:
        meetings_info = "\n\nYou have no upcoming meetings. Use /join to join a meeting."
    
    # Show profile
    await message.answer(
        f"📋 Your Profile:\n\n"
        f"Name: {user['name']}\n"
        f"Age: {user['age']}\n"
        f"City: {user['city']}\n"
        f"Description: {user['description']}\n"
        f"Registered: {user['registration_date'].strftime('%d.%m.%Y')}"
        f"{meetings_info}\n\n"
        f"To edit your profile, use /edit"
    )

# Edit profile command handler
@router.message(Command("edit"))
async def cmd_edit_profile(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Get user from database
    user = await get_user(user_id)
    
    if not user:
        await message.answer(
            "You are not registered yet. Please use /start to register."
        )
        return
    
    # Create keyboard with edit options
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Edit Name"), KeyboardButton(text="Edit Age")],
            [KeyboardButton(text="Edit City"), KeyboardButton(text="Edit Description")],
            [KeyboardButton(text="Cancel")]
        ],
        resize_keyboard=True
    )
    
    # Show edit menu
    await message.answer(
        "What would you like to edit?",
        reply_markup=keyboard
    )
    
    # Set state to menu
    await state.set_state(ProfileEditStates.menu)
    
    # Save current user data to state
    await state.update_data(
        current_name=user['name'],
        current_age=user['age'],
        current_city=user['city'],
        current_description=user['description']
    )

# Menu handler
@router.message(ProfileEditStates.menu, F.text == "Edit Name")
async def edit_name(message: Message, state: FSMContext):
    data = await state.get_data()
    await message.answer(f"Current name: {data['current_name']}\nEnter your new name:")
    await state.set_state(ProfileEditStates.name)

@router.message(ProfileEditStates.menu, F.text == "Edit Age")
async def edit_age(message: Message, state: FSMContext):
    data = await state.get_data()
    await message.answer(f"Current age: {data['current_age']}\nEnter your new age:")
    await state.set_state(ProfileEditStates.age)

@router.message(ProfileEditStates.menu, F.text == "Edit City")
async def edit_city(message: Message, state: FSMContext):
    data = await state.get_data()
    await message.answer(f"Current city: {data['current_city']}\nEnter your new city:")
    await state.set_state(ProfileEditStates.city)

@router.message(ProfileEditStates.menu, F.text == "Edit Description")
async def edit_description(message: Message, state: FSMContext):
    data = await state.get_data()
    await message.answer(f"Current description: {data['current_description']}\nEnter your new description:")
    await state.set_state(ProfileEditStates.description)

@router.message(ProfileEditStates.menu, F.text == "Cancel")
async def cancel_edit(message: Message, state: FSMContext):
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="/profile"), KeyboardButton(text="/join")]
        ],
        resize_keyboard=True
    )
    await message.answer("Profile editing cancelled.", reply_markup=keyboard)
    await state.clear()

# Field update handlers
@router.message(ProfileEditStates.name)
async def process_name(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Update name in database
    await update_user(user_id, name=message.text)
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="/profile"), KeyboardButton(text="/join")]
        ],
        resize_keyboard=True
    )
    
    await message.answer(f"Your name has been updated to: {message.text}", reply_markup=keyboard)
    await state.clear()

@router.message(ProfileEditStates.age)
async def process_age(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Validate age
    if not message.text.isdigit():
        await message.answer("Please enter a valid number for your age.")
        return
    
    age = int(message.text)
    if age < 18 or age > 100:
        await message.answer("Please enter a valid age between 18 and 100.")
        return
    
    # Update age in database
    await update_user(user_id, age=age)
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="/profile"), KeyboardButton(text="/join")]
        ],
        resize_keyboard=True
    )
    
    await message.answer(f"Your age has been updated to: {age}", reply_markup=keyboard)
    await state.clear()

@router.message(ProfileEditStates.city)
async def process_city(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Update city in database
    await update_user(user_id, city=message.text)
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="/profile"), KeyboardButton(text="/join")]
        ],
        resize_keyboard=True
    )
    
    await message.answer(f"Your city has been updated to: {message.text}", reply_markup=keyboard)
    await state.clear()

@router.message(ProfileEditStates.description)
async def process_description(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Update description in database
    await update_user(user_id, description=message.text)
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="/profile"), KeyboardButton(text="/join")]
        ],
        resize_keyboard=True
    )
    
    await message.answer("Your description has been updated.", reply_markup=keyboard)
    await state.clear()

# Function to register handlers with the dispatcher
def register_profile_handlers(dp):
    dp.include_router(router)