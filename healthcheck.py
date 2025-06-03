#!/usr/bin/env python3
import asyncio
import logging
import sys
import traceback
from datetime import datetime

from aiogram import Bot
from config import USER_BOT_TOKEN
from database.db import init_db, close_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

async def check_bot_token():
    """Check if the bot token is valid"""
    try:
        bot = Bot(token=USER_BOT_TOKEN)
        me = await bot.get_me()
        await bot.session.close()
        
        logger.info(f"Bot token is valid. Bot username: @{me.username}")
        return True
    except Exception as e:
        logger.error(f"Bot token is invalid: {e}")
        return False

async def check_database_connection():
    """Check if the database connection is working"""
    try:
        await init_db()
        logger.info("Database connection is working")
        await close_db()
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False

async def main():
    """Main function to check the bot's health"""
    logger.info("Starting health check...")
    
    # Check bot token
    bot_token_valid = await check_bot_token()
    
    # Check database connection
    db_connection_valid = await check_database_connection()
    
    # Print results
    logger.info("Health check results:")
    logger.info(f"Bot token: {'VALID' if bot_token_valid else 'INVALID'}")
    logger.info(f"Database connection: {'VALID' if db_connection_valid else 'INVALID'}")
    
    if bot_token_valid and db_connection_valid:
        logger.info("All checks passed! The bot is healthy.")
        return 0
    else:
        logger.error("Some checks failed. The bot may not work properly.")
        return 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Health check interrupted by user")
    except Exception as e:
        logger.critical(f"Fatal error during health check: {e}")
        logger.critical(traceback.format_exc())
        sys.exit(1)