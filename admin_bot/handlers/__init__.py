# Admin bot handlers package

import logging
from aiogram import Dispatcher

# Set up logger
logger = logging.getLogger(__name__)

# Import handlers
from admin_bot.handlers.start import register_start_handlers
from admin_bot.handlers.cities import register_cities_handlers
from admin_bot.handlers.timeslots import register_timeslots_handlers
from admin_bot.handlers.questions import register_questions_handlers
from admin_bot.handlers.applications import register_applications_handlers
from admin_bot.handlers.meetings import register_meetings_handlers
from admin_bot.handlers.venues import register_venues_handlers

# Command mapping for documentation and consistency
ADMIN_COMMANDS = {
    "/start": "Start the admin bot and authenticate",
    "/cities": "Manage cities",
    "/timeslots": "Manage time slots",
    "/questions": "Manage questions",
    "/applications": "Review applications",
    "/meetings": "Manage meetings",
    "/venues": "Manage venues",
    "/help": "Show help message",
    # Superadmin commands
    "/admins": "Manage administrators (superadmin only)",
    "/stats": "View system statistics (superadmin only)"
}

def register_admin_handlers(dp: Dispatcher):
    """Register all admin bot handlers"""
    logger.info("Registering admin bot handlers")
    
    # Register handlers in the correct order
    register_start_handlers(dp)
    register_cities_handlers(dp)
    register_timeslots_handlers(dp)
    register_questions_handlers(dp)
    register_applications_handlers(dp)
    register_meetings_handlers(dp)
    register_venues_handlers(dp)
    
    logger.info(f"Registered {len(ADMIN_COMMANDS)} admin commands")