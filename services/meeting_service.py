import logging
import asyncio
from datetime import datetime, date, time, timedelta

from database.db import (
    get_users_by_city, create_meeting, join_meeting, 
    get_pending_meetings_by_city, count_meeting_participants,
    get_meeting_participants, update_meeting, update_meeting_status
)
from config import MIN_MEETING_PARTICIPANTS

logger = logging.getLogger(__name__)

async def check_and_form_meetings():
    """
    Check for cities with enough users and form meetings if needed.
    This function should be run periodically (e.g., daily).
    """
    logger.info("Checking for potential meetings...")
    
    try:
        # Import here to avoid circular imports
        from database.db import pool
        
        # Get all cities with enough users
        async with pool.acquire() as conn:
            cities_with_users = await conn.fetch('''
                SELECT city, COUNT(*) as user_count
                FROM users
                WHERE city IS NOT NULL
                GROUP BY city
                HAVING COUNT(*) >= $1
            ''', MIN_MEETING_PARTICIPANTS)
        
        logger.info(f"Found {len(cities_with_users)} cities with enough users")
        
        for city_record in cities_with_users:
            city = city_record['city']
            user_count = city_record['user_count']
            
            # Get users in this city
            users = await get_users_by_city(city)
            
            # Check if there's already a pending meeting
            pending_meetings = await get_pending_meetings_by_city(city)
            
            if not pending_meetings:
                # No pending meeting, create one
                # Schedule it for next weekend at 18:00
                today = date.today()
                days_until_saturday = (5 - today.weekday()) % 7
                if days_until_saturday == 0:
                    days_until_saturday = 7  # If today is Saturday, schedule for next Saturday
                
                meeting_date = today + timedelta(days=days_until_saturday)
                meeting_time = time(18, 0)  # 6:00 PM
                
                meeting_id = await create_meeting(
                    location=city,
                    date=meeting_date,
                    time=meeting_time
                )
                
                logger.info(f"Created new meeting in {city} for {meeting_date}")
                
                # We don't automatically add users to meetings anymore
                # Instead, we'll notify them about the new meeting
                # and they can join if they want
                
                logger.info(f"Created meeting {meeting_id} in {city} with {user_count} potential participants")
    except Exception as e:
        logger.error(f"Error checking and forming meetings: {e}")

async def check_meeting_status():
    """
    Check the status of pending meetings and update if needed.
    This function should be run periodically (e.g., hourly).
    """
    logger.info("Checking meeting statuses...")
    
    try:
        # Import here to avoid circular imports
        from database.db import pool
        
        # Get all pending meetings
        async with pool.acquire() as conn:
            pending_meetings = await conn.fetch('''
                SELECT * FROM meetings
                WHERE status = 'pending'
            ''')
        
        logger.info(f"Found {len(pending_meetings)} pending meetings")
        
        for meeting in pending_meetings:
            # Get participant count
            participant_count = await count_meeting_participants(meeting['id'])
            
            # Check if meeting has enough participants
            if participant_count >= MIN_MEETING_PARTICIPANTS and meeting['status'] == 'pending':
                # Update meeting status to confirmed
                await update_meeting(meeting['id'], status='confirmed')
                
                # Get all participants
                participants = await get_meeting_participants(meeting['id'])
                
                # In a real bot, you would send a notification to each participant
                # that the meeting is now confirmed
                logger.info(f"Meeting {meeting['id']} in {meeting['location']} is now confirmed with {participant_count} participants")
                
                # Send confirmation to each participant
                for participant in participants:
                    await send_meeting_confirmation(participant['id'], meeting)
            
            # Check if meeting is approaching
            meeting_date = meeting['date']
            today = date.today()
            
            # If meeting is tomorrow, send reminder
            if (meeting_date - today).days == 1 and meeting['status'] == 'confirmed':
                # Get all participants
                participants = await get_meeting_participants(meeting['id'])
                
                # In a real bot, you would send a reminder to each participant
                logger.info(f"Sending reminders for meeting {meeting['id']} in {meeting['location']} tomorrow")
                
                # Send reminder to each participant
                for participant in participants:
                    await send_meeting_reminder(participant['id'], meeting)
            
            # Если встреча уже прошла и не отменена и не завершена, меняем статус на finished
            if meeting_date < today and meeting['status'] not in ('cancelled', 'finished'):
                await update_meeting_status(meeting['id'], 'finished')
                logger.info(f"Meeting {meeting['id']} marked as finished.")
    except Exception as e:
        logger.error(f"Error checking meeting status: {e}")

async def run_meeting_service():
    """
    Run the meeting service in the background.
    This function starts periodic tasks for checking and forming meetings.
    """
    logger.info("Starting meeting service...")
    
    while True:
        # Check for potential meetings
        await check_and_form_meetings()
        
        # Check meeting statuses
        await check_meeting_status()
        
        # Wait for next check (e.g., every hour)
        await asyncio.sleep(3600)  # 1 hour

# Helper functions for notifications

async def send_meeting_update(user_id, meeting_id, message):
    """
    Send a meeting update notification to a user.
    In a real bot, this would use the bot instance to send a message.
    """
    # This is a placeholder. In a real bot, you would:
    # await bot.send_message(user_id, message)
    logger.info(f"Notification to user {user_id} about meeting {meeting_id}: {message}")

async def send_meeting_reminder(user_id, meeting):
    """
    Send a meeting reminder to a user.
    In a real bot, this would use the bot instance to send a message.
    """
    # This is a placeholder. In a real bot, you would:
    # await bot.send_message(user_id, f"Reminder: You have a meeting tomorrow at {meeting['time']} in {meeting['location']}")
    logger.info(f"Reminder to user {user_id} about meeting {meeting['id']} tomorrow")

async def send_meeting_confirmation(user_id, meeting):
    """
    Send a meeting confirmation to a user.
    In a real bot, this would use the bot instance to send a message.
    """
    # This is a placeholder. In a real bot, you would:
    # await bot.send_message(user_id, f"Meeting confirmed: {meeting['date']} at {meeting['time']} in {meeting['location']}")
    logger.info(f"Confirmation to user {user_id} about meeting {meeting['id']} being confirmed")