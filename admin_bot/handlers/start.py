from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from config import ADMIN_IDS, SUPERADMIN_IDS
from database.db import add_admin, get_admin, is_admin, is_superadmin
from admin_bot.states import AdminAuthStates

# Create router
router = Router()

# Start command handler
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Check if user is an admin
    admin = await get_admin(user_id)
    
    if admin:
        # Admin already exists
        keyboard = create_admin_keyboard(admin['is_superadmin'])
        
        await message.answer(
            f"Welcome back, Admin {admin['name']}!\n\n"
            f"Use the commands below to manage the 5 Chairs system.",
            reply_markup=keyboard
        )
        return
    
    # Check if user is in the admin list
    if user_id in ADMIN_IDS or user_id in SUPERADMIN_IDS:
        # User is authorized to be an admin
        is_super = user_id in SUPERADMIN_IDS
        
        # Add admin to database
        await add_admin(
            admin_id=user_id,
            username=username,
            name=message.from_user.first_name,
            is_superadmin=is_super
        )
        
        # Create admin keyboard
        keyboard = create_admin_keyboard(is_super)
        
        await message.answer(
            f"Welcome, {'Super' if is_super else ''} Admin {message.from_user.first_name}!\n\n"
            f"You have been registered as an administrator for the 5 Chairs system.\n"
            f"Use the commands below to manage the system.",
            reply_markup=keyboard
        )
    else:
        # User is not authorized
        await message.answer(
            "Sorry, you are not authorized to use this bot.\n"
            "This bot is only for administrators of the 5 Chairs system."
        )

# Help command handler
@router.message(Command("help"))
async def cmd_help(message: Message):
    user_id = message.from_user.id
    
    # Check if user is an admin
    if not await is_admin(user_id):
        await message.answer(
            "Sorry, you are not authorized to use this bot.\n"
            "This bot is only for administrators of the 5 Chairs system."
        )
        return
    
    # Check if user is a superadmin
    is_super = await is_superadmin(user_id)
    
    # Basic commands for all admins
    help_text = (
        "5 Chairs Admin Bot Help:\n\n"
        "/start - Start the admin bot\n"
        "/cities - Manage cities\n"
        "/timeslots - Manage time slots\n"
        "/questions - Manage questions\n"
        "/applications - Review applications\n"
        "/meetings - Manage groups\n"
        "/help - Show this help message\n"
    )
    
    # Additional commands for superadmins
    if is_super:
        help_text += (
            "\nSuperadmin Commands:\n"
            "/admins - Manage administrators\n"
        )
    
    await message.answer(help_text)

# Function to create admin keyboard
def create_admin_keyboard(is_superadmin=False):
    """Create keyboard with admin commands"""
    keyboard = [
        [KeyboardButton(text="/cities"), KeyboardButton(text="/timeslots")],
        [KeyboardButton(text="/questions"), KeyboardButton(text="/applications")],
        [KeyboardButton(text="/meetings"), KeyboardButton(text="/venues")]
    ]
    
    # Add superadmin commands
    if is_superadmin:
        keyboard.append([KeyboardButton(text="/admins")])
    
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True
    )

# Function to send admin menu
async def send_admin_menu(message: Message):
    """Send admin menu to user"""
    user_id = message.from_user.id
    
    # Check if user is an admin
    admin = await get_admin(user_id)
    
    if not admin:
        await message.answer("You are not authorized to use this bot.")
        return
    
    # Create keyboard based on admin level
    keyboard = create_admin_keyboard(admin.get('is_superadmin', False))
    
    await message.answer(
        f"Welcome to the Admin Bot, {admin['name']}!\n\n"
        f"Use the commands below to manage the system:",
        reply_markup=keyboard
    )

# Function to register handlers with the dispatcher
def register_start_handlers(dp):
    dp.include_router(router)