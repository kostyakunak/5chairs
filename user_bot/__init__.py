# User bot package

from aiogram import Dispatcher
from user_bot.handlers import register_user_handlers

def setup_user_bot(dp: Dispatcher):
    """Setup user bot by registering all handlers"""
    register_user_handlers(dp)