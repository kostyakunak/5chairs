import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from config import USER_BOT_TOKEN, ADMIN_BOT_TOKEN
from database.db import init_db, close_db
from services.notification_service import run_notification_service

# Configure logging
import os
from datetime import datetime

# Create logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)

# Get current date for log filename
current_date = datetime.now().strftime("%Y-%m-%d")

# Configure logging to both console and file
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),  # Log to console
        logging.FileHandler(f"logs/{current_date}.log")  # Log to file
    ]
)
logger = logging.getLogger(__name__)

async def set_user_bot_commands(bot: Bot):
    """Set commands for the user bot"""
    commands = [
        BotCommand(command="/start", description="Start the bot and register"),
        BotCommand(command="/menu", description="Show main menu"),
        BotCommand(command="/my_meetings", description="My meetings"),
        BotCommand(command="/apply", description="Apply for a meeting (legacy)"),
        BotCommand(command="/help", description="Get help"),
    ]
    await bot.set_my_commands(commands)

async def set_admin_bot_commands(bot: Bot):
    """Set commands for the admin bot"""
    commands = [
        BotCommand(command="/start", description="Start the admin bot"),
        BotCommand(command="/cities", description="Manage cities"),
        BotCommand(command="/timeslots", description="Manage time slots"),
        BotCommand(command="/questions", description="Manage questions"),
        BotCommand(command="/applications", description="Review applications"),
        BotCommand(command="/meetings", description="Manage meetings"),
        BotCommand(command="/help", description="Get help"),
    ]
    await bot.set_my_commands(commands)

async def main():
    """Main function to start both bots"""
    # Check command line arguments
    if len(sys.argv) < 2:
        print("Usage: python main.py [user|admin|notification]")
        return
    
    mode = sys.argv[1].lower()
    
    # Initialize database connection
    await init_db()
    
    try:
        if mode == "user":
            # Start user bot
            logger.info("Starting user bot")
            
            # Initialize bot and dispatcher
            bot = Bot(token=USER_BOT_TOKEN)
            dp = Dispatcher(storage=MemoryStorage())
            
            # Import and setup user bot
            from user_bot import setup_user_bot
            
            # Register all user handlers
            setup_user_bot(dp)
            
            # Set bot commands
            await set_user_bot_commands(bot)
            
            # Start polling
            logger.info("User bot started")
            await dp.start_polling(bot)
            
        elif mode == "admin":
            # Start admin bot
            logger.info("Starting admin bot")
            
            # Initialize bot and dispatcher
            bot = Bot(token=ADMIN_BOT_TOKEN)
            dp = Dispatcher(storage=MemoryStorage())
            
            # Import and setup admin bot
            from admin_bot import setup_admin_bot
            
            # Register all admin handlers
            setup_admin_bot(dp)
            
            # Set bot commands
            await set_admin_bot_commands(bot)
            
            # Start polling
            logger.info("Admin bot started")
            await dp.start_polling(bot)
            
        elif mode == "notification":
            # Start notification service
            logger.info("Starting notification service")
            
            # Initialize bot
            bot = Bot(token=USER_BOT_TOKEN)
            
            # Run notification service
            await run_notification_service(bot)
            
        else:
            logger.error(f"Unknown mode: {mode}")
            print("Usage: python main.py [user|admin|notification]")
    
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")
    except Exception as e:
        logger.exception(f"Error: {e}")
    finally:
        # Close database connection
        await close_db()

if __name__ == "__main__":
    asyncio.run(main())