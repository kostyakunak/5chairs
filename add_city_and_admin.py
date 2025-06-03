#!/usr/bin/env python3
import asyncio
import sys
import os
from datetime import datetime

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.db import init_db, add_city, add_admin, close_db

async def add_initial_data():
    """Add initial data to the database"""
    print("Initializing database...")
    await init_db()
    
    # Add a city
    print("Adding Warsaw as a city...")
    try:
        city_id = await add_city("Warsaw", active=True)
        print(f"City added with ID: {city_id}")
    except Exception as e:
        print(f"Error adding city: {e}")
    
    # Add more cities if needed
    for city_name in ["Krakow", "Gdansk", "Wroclaw", "Poznan"]:
        try:
            city_id = await add_city(city_name, active=True)
            print(f"City {city_name} added with ID: {city_id}")
        except Exception as e:
            print(f"Error adding city {city_name}: {e}")
    
    # Close database connection
    await close_db()
    print("Database connection closed")

def update_admin_ids():
    """Update admin IDs in config.py"""
    print("Enter your Telegram user ID to add as admin:")
    admin_id = input("> ")
    
    if not admin_id.isdigit():
        print("Error: Admin ID must be a number")
        return
    
    # Read the current config.py file
    with open("config.py", "r") as f:
        config_content = f.read()
    
    # Replace the default admin ID with the provided one
    config_content = config_content.replace(
        'ADMIN_IDS_STR = os.getenv("ADMIN_IDS", "123456789")',
        f'ADMIN_IDS_STR = os.getenv("ADMIN_IDS", "{admin_id}")'
    )
    
    # Replace the default superadmin ID with the provided one
    config_content = config_content.replace(
        'SUPERADMIN_IDS_STR = os.getenv("SUPERADMIN_IDS", "123456789")',
        f'SUPERADMIN_IDS_STR = os.getenv("SUPERADMIN_IDS", "{admin_id}")'
    )
    
    # Write the updated content back to config.py
    with open("config.py", "w") as f:
        f.write(config_content)
    
    print(f"Admin ID {admin_id} added to config.py")
    print("You can now restart the admin bot and use /start to authenticate")

if __name__ == "__main__":
    print("5 Chairs - Initial Setup")
    print("------------------------")
    print("This script will add initial data to the database and update admin IDs")
    
    # Add cities to the database
    asyncio.run(add_initial_data())
    
    # Update admin IDs in config.py
    update_admin_ids()
    
    print("\nSetup complete!")
    print("You can now run the bots with:")
    print("  python run_user_bot.py")
    print("  python run_admin_bot.py")
    print("  python run_notification_service.py")