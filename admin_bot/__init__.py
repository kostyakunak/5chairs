# Admin bot package

from aiogram import Dispatcher
from admin_bot.handlers import register_admin_handlers

def setup_admin_bot(dp: Dispatcher):
    """Setup admin bot by registering all handlers"""
    register_admin_handlers(dp)