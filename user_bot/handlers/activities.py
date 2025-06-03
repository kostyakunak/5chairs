import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Set up logger
logger = logging.getLogger(__name__)

# Import handlers from events and application
# from user_bot.handlers.events import cmd_applications  # Удалено, функция больше не существует
# from user_bot.handlers.meetings import cmd_meetings  # Удалено, функция больше не существует

# Create router
router = Router()

# Activities command handler
@router.message(Command("activities"))
async def cmd_activities(message: Message, state: FSMContext):
    """Combined view of events, applications, and meetings"""
    user_id = message.from_user.id
    logger.info(f"User {user_id} requested activities")
    
    # Create activities menu
    builder = InlineKeyboardBuilder()
    builder.button(text="View My Applications", callback_data="view_applications")
    builder.button(text="Main Menu", callback_data="main_menu")
    builder.adjust(1)
    
    await message.answer(
        "🪑 5 Chairs Activities 🪑\n\n"
        "Welcome to the activities center! Here you can check your applications.\n\n"
        "What would you like to do?",
        reply_markup=builder.as_markup()
    )

# View meetings handler
@router.callback_query(F.data == "view_meetings")
async def view_meetings(callback: CallbackQuery):
    """View meetings"""
    await callback.answer()
    await callback.message.answer("Viewing meetings is no longer available. Please use Apply to participate in events.")
    # Add back button
    builder = InlineKeyboardBuilder()
    builder.button(text="Back to Activities", callback_data="back_to_activities")
    builder.adjust(1)
    await callback.message.answer(
        "Use the button below to return to the activities menu:",
        reply_markup=builder.as_markup()
    )

# Back to activities handler
@router.callback_query(F.data == "back_to_activities")
async def back_to_activities(callback: CallbackQuery):
    """Return to activities menu"""
    await callback.answer()
    
    # Call the activities command
    await cmd_activities(callback.message, None)

# Function to register handlers with the dispatcher
def register_activities_handlers(dp):
    logger.info("Registering activities handlers")
    dp.include_router(router)