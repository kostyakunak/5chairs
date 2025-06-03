# Configuration file for the 5 Chairs Telegram bots
import os
from typing import List
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Bot tokens
USER_BOT_TOKEN = os.getenv("USER_BOT_TOKEN", "7871145012:AAHi55dUuleA_sm5ZfIJ7MCL4hJhESeF2Ao")
# Admin bot token provided by the user
ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN", "7526928704:AAFPC1M2XrgfIcm7XPrbxmRsa173urX6mkk")

# Database configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "five_chairs")
DB_USER = os.getenv("DB_USER", "kostakunak")  # Updated to use the correct PostgreSQL user
DB_PASSWORD = os.getenv("DB_PASSWORD", "")  # Empty password for local development

# Admin settings
ADMIN_IDS_STR = os.getenv("ADMIN_IDS", "5778834899")
ADMIN_IDS = [int(admin_id.strip()) for admin_id in ADMIN_IDS_STR.split(",") if admin_id.strip()]
SUPERADMIN_IDS_STR = os.getenv("SUPERADMIN_IDS", "5778834899")
SUPERADMIN_IDS = [int(admin_id.strip()) for admin_id in SUPERADMIN_IDS_STR.split(",") if admin_id.strip()]

# Application settings
MIN_MEETING_SIZE = int(os.getenv("MIN_MEETING_SIZE", "5"))
MAX_MEETING_SIZE = int(os.getenv("MAX_MEETING_SIZE", "5"))

# Notification settings
REMINDER_DAY_BEFORE = os.getenv("REMINDER_DAY_BEFORE", "true").lower() == "true"
REMINDER_HOUR_BEFORE = os.getenv("REMINDER_HOUR_BEFORE", "true").lower() == "true"