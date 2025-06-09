# User bot handlers package

import logging
from aiogram import Dispatcher

# Set up logger
logger = logging.getLogger(__name__)

# Import handlers
from user_bot.handlers.start import register_start_handlers
from user_bot.handlers.application import router as application_router
# from user_bot.handlers.profile import register_profile_handlers  # Удалено
# from user_bot.handlers.application import register_application_handlers
from user_bot.handlers.meetings import register_meetings_handlers
# from user_bot.handlers.events import register_events_handlers
from user_bot.handlers.activities import register_activities_handlers

# Command mapping for documentation and consistency
USER_COMMANDS = {
    "/start": "Start the bot and register",
    "/menu": "Show the main menu",
    # "/profile": "View and edit your profile",  # Удалено
    "Apply": "Select a date and time for your activity and submit your application",
    "/applications": "View all your applications",
    "/help": "Show help message",
    # Deprecated commands (kept for backward compatibility)
    "/meetings": "View your meetings (use Apply instead)",
    "/apply": "Old application system (use Apply instead)",
    "/status": "Old status check (use /applications instead)"
}

def register_user_handlers(dp: Dispatcher):
    """Register all user bot handlers"""
    logger.info("Registering user bot handlers")
    
    # Register handlers in the correct order
    register_start_handlers(dp)
    dp.include_router(application_router)
    # register_profile_handlers(dp)  # Удалено
    register_activities_handlers(dp)
    # register_events_handlers(dp)
    # register_application_handlers(dp)
    register_meetings_handlers(dp)
    
    logger.info(f"Registered {len(USER_COMMANDS)} user commands")