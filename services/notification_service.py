import logging
import asyncio
from datetime import datetime, date, timedelta, time

from database.db import get_pool, init_db, get_meeting_members
from services.timeslot_service import timeslot_service  # Импортируем сервис таймслотов

logger = logging.getLogger(__name__)

class NotificationService:
    """Service for sending notifications to users"""
    
    def __init__(self, bot):
        """Initialize with bot instance"""
        self.bot = bot
        self.logger = logging.getLogger(__name__)
    
    async def _get_conn(self):
        pool_obj = await get_pool()
        return pool_obj
    
    async def send_message(self, user_id, text):
        """Send a message to a user"""
        try:
            await self.bot.send_message(user_id, text)
            self.logger.info(f"Sent message to user {user_id}")
        except Exception as e:
            self.logger.error(f"Failed to send message to user {user_id}: {e}")
    
    async def send_application_status_update(self, user_id, status, admin_notes=None, meeting_id=None):
        """Send an application status update to a user, optionally with meeting assignment and time preference details"""
        status_emoji = {
            "approved": "✅",
            "rejected": "❌"
        }
        
        text = (
            f"{status_emoji.get(status, '')} Your application has been {status}!\n\n"
        )
        
        if status == "approved":
            # If meeting_id is provided, this is an approval with immediate meeting assignment
            if meeting_id:
                pool_obj = await self._get_conn()
                async with pool_obj.acquire() as conn:
                    meeting = await conn.fetchrow('''
                        SELECT g.id, g.name, g.meeting_date, g.meeting_time, g.venue, c.name as city_name
                        FROM meetings g
                        JOIN cities c ON g.city_id = c.id
                        WHERE g.id = $1
                    ''', meeting_id)
                    
                    # Get meeting members
                    members = await conn.fetch('''
                        SELECT u.name, u.surname
                        FROM meeting_members mm
                        JOIN users u ON mm.user_id = u.id
                        WHERE mm.meeting_id = $1
                        ORDER BY u.name, u.surname
                    ''', meeting_id)
                
                if meeting:
                    # Format member list
                    member_list = ""
                    for i, member in enumerate(members, 1):
                        member_list += f"{i}. {member['name']} {member['surname']}\n"
                    
                    text += (
                        "🎉 Congratulations! Your application has been approved and you've been "
                        "added to a discussion meeting!\n\n"
                        f"Meeting: {meeting['name']}\n"
                        f"📍 Location: {meeting['city_name']} - {meeting['venue']}\n"
                        f"📅 Date: {meeting['meeting_date'].strftime('%A, %d.%m.%Y')}\n"
                        f"🕕 Time: {meeting['meeting_time'].strftime('%H:%M')}\n\n"
                        f"Meeting Members:\n{member_list}\n"
                        f"We've matched you with these participants based on your interests and preferences. "
                        f"You'll be participating in a meaningful discussion using the 5 Chairs method.\n\n"
                        f"You'll receive a reminder one day before and one hour before the meeting.\n\n"
                        f"Use /meetings to see all your upcoming meetings.\n"
                        f"Use /applications to view all your application statuses."
                    )
                else:
                    # Fallback if group details can't be retrieved
                    text += (
                        "🎉 Congratulations! Your application has been approved and you've been "
                        "added to a discussion meeting!\n\n"
                        "You'll receive more details about your meeting shortly.\n\n"
                        "Thank you for your participation in the 5 Chairs discussion group!\n"
                        f"Use /applications to view all your application statuses."
                    )
            else:
                # Standard approval without group assignment
                text += (
                    "🎉 Congratulations! Your application has been approved.\n\n"
                    "We are now in the process of matching you with other participants "
                    "based on your interests and preferences. You will be notified soon "
                    "when you are added to a group.\n\n"
                    "⏱️ Estimated waiting time: 1-3 days for group assignment.\n\n"
                    "Thank you for your patience and we look forward to your participation "
                    "in the 5 Chairs discussion group!\n"
                    f"Use /applications to view all your application statuses and check for updates."
                )
        elif status == "rejected":
            text += (
                "Unfortunately, your application has not been approved at this time.\n\n"
                "This could be due to various reasons such as group capacity or "
                "matching criteria. We encourage you to apply again for future meetings.\n\n"
                "You can browse available events and create a new application with /events.\n"
                "Use /applications to view all your application statuses."
            )
        
        if admin_notes:
            text += f"\n\n📝 Feedback from the organizer: {admin_notes}"
        
        # Send the message with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                pool_obj = await self._get_conn()
                async with pool_obj.acquire() as conn:
                    await conn.execute('''
                        INSERT INTO notifications (user_id, text, status)
                        VALUES ($1, $2, $3)
                    ''', user_id, text, status)
                self.logger.info(f"Successfully sent notification to user {user_id} (attempt {attempt+1})")
                return True
            except Exception as e:
                self.logger.error(f"Failed to send notification to user {user_id} (attempt {attempt+1}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)  # Wait before retrying
                else:
                    self.logger.error(f"All attempts to send notification to user {user_id} failed")
                    return False
    
    async def send_group_invitation(self, user_id, group):
        """Send a group invitation to a user"""
        text = (
            f"🎉 You've been added to a new group!\n\n"
            f"Group: {group['name']}\n"
            f"📍 Location: {group['city_name']} - {group['venue']}\n"
            f"📅 Date: {group['meeting_date'].strftime('%A, %d.%m.%Y')}\n"
            f"🕕 Time: {group['meeting_time'].strftime('%H:%M')}\n\n"
            f"We've matched you with other participants based on your interests and preferences. "
            f"You'll be meeting with a small group of 5 people for a meaningful discussion.\n\n"
            f"📋 Meeting Agenda:\n"
            f"- Introduction and ice-breakers (15 min)\n"
            f"- 5 Chairs method explanation (10 min)\n"
            f"- Main discussion (60 min)\n"
            f"- Wrap-up and next steps (15 min)\n\n"
            f"You'll receive a reminder one day before and one hour before the meeting.\n\n"
            f"Use /meetings to see all your upcoming meetings.\n"
            f"Use /applications to view all your application statuses."
        )
        await self.send_message(user_id, text)
    
    async def send_meeting_assignment(self, user_id, meeting_id):
        """Send a meeting assignment notification to a user with time preference details"""
        pool_obj = await self._get_conn()
        async with pool_obj.acquire() as conn:
            # Get meeting details with time slot information
            meeting = await conn.fetchrow('''
                SELECT m.*, c.name as city_name, ts.day_of_week, ts.start_time, ts.end_time
                FROM meetings m
                JOIN cities c ON m.city_id = c.id
                JOIN meeting_time_slots mts ON m.id = mts.meeting_id
                JOIN time_slots ts ON mts.time_slot_id = ts.id
                WHERE m.id = $1
            ''', meeting_id)
            
            if not meeting:
                # Fallback to basic method if meeting details can't be retrieved with time slot
                return await self.send_application_status_update(user_id, "approved", None, meeting_id)
            
            # Get meeting members
            members = await conn.fetch('''
                SELECT u.name, u.surname
                FROM meeting_members mm
                JOIN users u ON mm.user_id = u.id
                WHERE mm.meeting_id = $1
                ORDER BY u.name, u.surname
            ''', meeting_id)
            
            # Format member list
            member_list = ""
            for i, member in enumerate(members, 1):
                member_list += f"{i}. {member['name']} {member['surname']}\n"
            
            text = (
                f"🎉 You've been added to a new meeting based on your time preferences!\n\n"
                f"Meeting: {meeting['name']}\n"
                f"📍 Location: {meeting['city_name']} - {meeting['venue']}\n"
                f"📅 Date: {meeting['meeting_date'].strftime('%A, %d.%m.%Y')}\n"
                f"🕕 Time: {meeting['meeting_time'].strftime('%H:%M')}\n"
                f"⏰ Time Preference: {meeting['day_of_week']} {meeting['start_time'].strftime('%H:%M')}-{meeting['end_time'].strftime('%H:%M')}\n\n"
                f"Meeting Members:\n{member_list}\n"
                f"We've matched you with these participants based on your time preferences. "
                f"You'll be participating in a meaningful discussion using the 5 Chairs method.\n\n"
                f"You'll receive a reminder one day before and one hour before the meeting.\n\n"
                f"Use /my_meetings to see all your upcoming meetings."
            )
            
            # Send the message with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    await conn.execute('''
                        INSERT INTO notifications (user_id, text, status)
                        VALUES ($1, $2, $3)
                    ''', user_id, text, "approved")
                    self.logger.info(f"Successfully sent meeting assignment to user {user_id} (attempt {attempt+1})")
                    return True
                except Exception as e:
                    self.logger.error(f"Failed to send meeting assignment to user {user_id} (attempt {attempt+1}): {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1)  # Wait before retrying
                    else:
                        self.logger.error(f"All attempts to send meeting assignment to user {user_id} failed")
                        return False
    
    async def send_meeting_update(self, user_id, meeting, message):
        """Send a meeting update to a user"""
        text = (
            f"📢 Meeting update: {meeting['name']}\n\n"
            f"📍 Location: {meeting['city_name']} - {meeting['venue']}\n"
            f"📅 Date: {meeting['meeting_date'].strftime('%A, %d.%m.%Y')}\n"
            f"🕕 Time: {meeting['meeting_time'].strftime('%H:%M')}\n\n"
            f"{message}"
        )
        await self.send_message(user_id, text)
    
    async def send_meeting_cancellation(self, user_id, meeting):
        """Send a meeting cancellation to a user"""
        text = (
            f"❌ Meeting cancelled: {meeting['name']}\n\n"
            f"The meeting in {meeting['city_name']} on {meeting['meeting_date'].strftime('%A, %d.%m.%Y')} "
            f"at {meeting['meeting_time'].strftime('%H:%M')} has been cancelled.\n\n"
            f"We apologize for any inconvenience."
        )
        await self.send_message(user_id, text)
    
    async def send_day_before_reminder(self, user_id, meeting):
        """Send a day before reminder to a user with time preference details"""
        # Check if meeting includes time slot information
        time_slot_info = ""
        
        # Try to get time slot information for this meeting
        try:
            pool_obj = await self._get_conn()
            async with pool_obj.acquire() as conn:
                time_slot = await conn.fetchrow('''
                    SELECT ts.day_of_week, ts.start_time, ts.end_time
                    FROM meeting_time_slots mts
                    JOIN time_slots ts ON mts.time_slot_id = ts.id
                    WHERE mts.meeting_id = $1
                    LIMIT 1
                ''', meeting['id'])
                
                if time_slot:
                    time_slot_info = f"\n⏰ Time Preference: {time_slot['day_of_week']} {time_slot['start_time'].strftime('%H:%M')}-{time_slot['end_time'].strftime('%H:%M')}"
        except Exception as e:
            self.logger.error(f"Error retrieving time slot info for meeting {meeting['id']}: {e}")
        
        # Get other members of the meeting
        members_info = ""
        try:
            pool_obj = await self._get_conn()
            async with pool_obj.acquire() as conn:
                members = await conn.fetch('''
                    SELECT u.id as user_id, u.name, u.surname
                    FROM meeting_members mm
                    JOIN users u ON mm.user_id = u.id
                    WHERE mm.meeting_id = $1
                    ORDER BY u.name, u.surname
                ''', meeting['id'])
                
                if members:
                    members_info = "\n\nOther participants:\n"
                    count = 0
                    for member in members:
                        if member['user_id'] != user_id:  # Skip the current user
                            count += 1
                            if count <= 5:  # Limit to first 5 other members
                                members_info += f"{count}. {member['name']} {member['surname']}\n"
                    
                    if count > 5:  # If there are more than 5 other members
                        members_info += f"...and {count - 5} more\n"
        except Exception as e:
            self.logger.error(f"Error retrieving members for meeting {meeting['id']}: {e}")
        
        text = (
            f"⏰ Reminder: You have a meeting tomorrow!\n\n"
            f"Meeting: {meeting['name']}\n"
            f"📍 Location: {meeting['city_name']} - {meeting['venue']}"
        )
        
        # Add address if available
        if meeting.get('venue_address'):
            text += f"\n📌 Address: {meeting['venue_address']}"
            
        text += (
            f"\n📅 Date: {meeting['meeting_date'].strftime('%A, %d.%m.%Y')}\n"
            f"🕕 Time: {meeting['meeting_time'].strftime('%H:%M')}"
            f"{time_slot_info}"
            f"{members_info}\n\n"
            f"📋 Meeting Agenda:\n"
            f"- Introduction and ice-breakers (15 min)\n"
            f"- 5 Chairs method explanation (10 min)\n"
            f"- Main discussion (60 min)\n"
            f"- Wrap-up and next steps (15 min)\n\n"
            f"Please arrive 5-10 minutes early to get settled.\n"
            f"We look forward to seeing you there!\n\n"
            f"Use /my_meetings to see details about all your upcoming meetings."
        )
        
        # Send the message with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                pool_obj = await self._get_conn()
                async with pool_obj.acquire() as conn:
                    await conn.execute('''
                        INSERT INTO notifications (user_id, text, status)
                        VALUES ($1, $2, $3)
                    ''', user_id, text, "reminder")
                self.logger.info(f"Successfully sent day-before reminder to user {user_id} (attempt {attempt+1})")
                return True
            except Exception as e:
                self.logger.error(f"Failed to send day-before reminder to user {user_id} (attempt {attempt+1}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)  # Wait before retrying
                else:
                    self.logger.error(f"All attempts to send day-before reminder to user {user_id} failed")
                    return False
    
    async def send_hour_before_reminder(self, user_id, meeting):
        """Send an hour before reminder to a user with venue address and time preference details"""
        # Try to get time slot information for this meeting
        time_slot_info = ""
        try:
            pool_obj = await self._get_conn()
            async with pool_obj.acquire() as conn:
                time_slot = await conn.fetchrow('''
                    SELECT ts.day_of_week, ts.start_time, ts.end_time
                    FROM meeting_time_slots mts
                    JOIN time_slots ts ON mts.time_slot_id = ts.id
                    WHERE mts.meeting_id = $1
                    LIMIT 1
                ''', meeting['id'])
                
                if time_slot:
                    time_slot_info = f"\n⏰ Scheduled preference: {time_slot['day_of_week']} {time_slot['start_time'].strftime('%H:%M')}-{time_slot['end_time'].strftime('%H:%M')}"
        except Exception as e:
            self.logger.error(f"Error retrieving time slot info for meeting {meeting['id']}: {e}")
        
        text = (
            f"⏰ Reminder: You have a meeting in 1 hour!\n\n"
            f"Meeting: {meeting['name']}\n"
            f"📍 Location: {meeting['city_name']} - {meeting['venue']}"
        )
        
        # Add address if available
        if meeting.get('venue_address'):
            text += f"\n📌 Address: {meeting['venue_address']}"
            
        text += (
            f"\n📅 Date: {meeting['meeting_date'].strftime('%A, %d.%m.%Y')}\n"
            f"🕕 Time: {meeting['meeting_time'].strftime('%H:%M')}"
            f"{time_slot_info}\n\n"
            f"Please arrive 5-10 minutes early to get settled.\n"
            f"We're looking forward to a great discussion!\n"
            f"Don't be late!\n\n"
            f"Use /my_meetings for meeting details."
        )
        
        # Send the message with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                pool_obj = await self._get_conn()
                async with pool_obj.acquire() as conn:
                    await conn.execute('''
                        INSERT INTO notifications (user_id, text, status)
                        VALUES ($1, $2, $3)
                    ''', user_id, text, "reminder")
                self.logger.info(f"Successfully sent hour-before reminder to user {user_id} (attempt {attempt+1})")
                return True
            except Exception as e:
                self.logger.error(f"Failed to send hour-before reminder to user {user_id} (attempt {attempt+1}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)  # Wait before retrying
                else:
                    self.logger.error(f"All attempts to send hour-before reminder to user {user_id} failed")
                    return False

    async def notify_user_added_to_meeting(self, user_id, meeting_id):
        """Notify a user that they've been added to a meeting based on time preferences"""
        pool_obj = await self._get_conn()
        async with pool_obj.acquire() as conn:
            # Get meeting details with time slot information
            meeting = await conn.fetchrow('''
                SELECT m.*, c.name as city_name, ts.day_of_week, ts.start_time, ts.end_time
                FROM meetings m
                JOIN cities c ON m.city_id = c.id
                LEFT JOIN meeting_time_slots mts ON m.id = mts.meeting_id
                LEFT JOIN time_slots ts ON mts.time_slot_id = ts.id
                WHERE m.id = $1
            ''', meeting_id)
            
            if not meeting:
                # Fallback to basic query if time slot join fails
                meeting = await conn.fetchrow('''
                    SELECT m.*, c.name as city_name
                    FROM meetings m
                    JOIN cities c ON m.city_id = c.id
                    WHERE m.id = $1
                ''', meeting_id)
                
            # Get meeting members
            members = await conn.fetch('''
                SELECT u.name, u.surname
                FROM meeting_members mm
                JOIN users u ON mm.user_id = u.id
                WHERE mm.meeting_id = $1
                ORDER BY u.name, u.surname
                LIMIT 6
            ''', meeting_id)
        
        if not meeting:
            self.logger.error(f"Failed to get meeting details for notification, meeting_id: {meeting_id}")
            return False
        
        # Format time preference info if available
        time_preference_info = ""
        if meeting.get('day_of_week') and meeting.get('start_time') and meeting.get('end_time'):
            time_preference_info = (
                f"\n⏰ Time Preference: {meeting['day_of_week']} "
                f"{meeting['start_time'].strftime('%H:%M')}-{meeting['end_time'].strftime('%H:%M')}"
            )
        
        # Format member list
        member_list = ""
        if members:
            member_list = "\n\nOther participants:\n"
            for i, member in enumerate(members, 1):
                if i <= 5:  # Limit to 5 members for readability
                    member_list += f"{i}. {member['name']} {member['surname']}\n"
            
            # Get total member count
            total_members = await conn.fetchval(
                'SELECT COUNT(*) FROM meeting_members WHERE meeting_id = $1',
                meeting_id
            )
            
            if total_members > 6:  # If there are more members than we display
                member_list += f"...and {total_members - 6} more\n"
        
        text = (
            f"🎉 You've been added to a new meeting based on your time preferences!\n\n"
            f"Meeting: {meeting['name']}\n"
            f"📍 Location: {meeting['city_name']} - {meeting['venue']}"
        )
        
        # Add address if available
        if meeting.get('venue_address'):
            text += f"\n📌 Address: {meeting['venue_address']}"
            
        text += (
            f"\n📅 Date: {meeting['meeting_date'].strftime('%A, %d.%m.%Y')}\n"
            f"🕕 Time: {meeting['meeting_time'].strftime('%H:%M')}"
            f"{time_preference_info}"
            f"{member_list}\n\n"
            f"We've matched you with these participants based on your time preferences. "
            f"You'll be participating in a meaningful discussion using the 5 Chairs method.\n\n"
            f"You'll receive a reminder one day before and one hour before the meeting.\n\n"
            f"Use /my_meetings to see all your upcoming meetings."
        )
        
        # Send the message with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                pool_obj = await self._get_conn()
                async with pool_obj.acquire() as conn:
                    await conn.execute('''
                        INSERT INTO notifications (user_id, text, status)
                        VALUES ($1, $2, $3)
                    ''', user_id, text, "approved")
                self.logger.info(f"Successfully sent meeting assignment notification to user {user_id} (attempt {attempt+1})")
                return True
            except Exception as e:
                self.logger.error(f"Failed to send meeting assignment to user {user_id} (attempt {attempt+1}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)  # Wait before retrying
                else:
                    self.logger.error(f"All attempts to send meeting assignment to user {user_id} failed")
                    return False
    
    async def notify_user_removed_from_meeting(self, user_id, meeting_id):
        """Notify a user that they've been removed from a meeting"""
        pool_obj = await self._get_conn()
        async with pool_obj.acquire() as conn:
            meeting = await conn.fetchrow('''
                SELECT g.*, c.name as city_name
                FROM meetings g
                JOIN cities c ON g.city_id = c.id
                WHERE g.id = $1
            ''', meeting_id)
        
        if meeting:
            text = (
                f"❗ You've been removed from a meeting\n\n"
                f"Meeting: {meeting['name']}\n"
                f"📅 Date: {meeting['meeting_date'].strftime('%A, %d.%m.%Y')}\n"
                f"🕕 Time: {meeting['meeting_time'].strftime('%H:%M')}\n\n"
                f"If you believe this is an error, please contact the administrator."
            )
            await self.send_message(user_id, text)
    
    async def notify_meeting_confirmed(self, meeting_id):
        """Notify all members of a meeting that it's been confirmed"""
        # Get meeting details
        pool_obj = await self._get_conn()
        async with pool_obj.acquire() as conn:
            meeting = await conn.fetchrow('''
                SELECT g.*, c.name as city_name
                FROM meetings g
                JOIN cities c ON g.city_id = c.id
                WHERE g.id = $1
            ''', meeting_id)
        
        if meeting:
            # Get all members
            members = await get_meeting_members(meeting_id)
            
            text = (
                f"✅ Meeting confirmed: {meeting['name']}\n\n"
                f"Your meeting has been confirmed!\n\n"
                f"📍 Location: {meeting['city_name']} - {meeting['venue']}\n"
                f"📅 Date: {meeting['meeting_date'].strftime('%A, %d.%m.%Y')}\n"
                f"🕕 Time: {meeting['meeting_time'].strftime('%H:%M')}\n\n"
                f"You'll receive a reminder one day before and one hour before the meeting.\n"
                f"We look forward to seeing you there!"
            )
            
            # Send notification to each member
            for member in members:
                await self.send_message(member['user_id'], text)
    
    async def notify_meeting_cancelled(self, meeting_id):
        """Notify all members of a meeting that it's been cancelled"""
        # Get meeting details
        pool_obj = await self._get_conn()
        async with pool_obj.acquire() as conn:
            meeting = await conn.fetchrow('''
                SELECT g.*, c.name as city_name
                FROM meetings g
                JOIN cities c ON g.city_id = c.id
                WHERE g.id = $1
            ''', meeting_id)
        
        if meeting:
            # Get all members
            members = await get_meeting_members(meeting_id)
            
            text = (
                f"❌ Meeting cancelled: {meeting['name']}\n\n"
                f"The meeting scheduled for {meeting['meeting_date'].strftime('%A, %d.%m.%Y')} "
                f"at {meeting['meeting_time'].strftime('%H:%M')} in {meeting['city_name']} "
                f"has been cancelled.\n\n"
                f"We apologize for any inconvenience."
            )
            
            # Send notification to each member
            for member in members:
                await self.send_message(member['user_id'], text)

async def run_notification_service(bot):
    """
    Run the notification service in the background.
    This function starts periodic tasks for sending notifications.
    """
    notification_service = NotificationService(bot)
    logger.info("Starting notification service...")
    
    # Запуск первоначального обновления доступных дат
    await update_available_dates()
    
    # Переменная для отслеживания последнего дня обновления доступных дат
    last_update_day = date.today().day
    
    while True:
        try:
            # Проверка для ежедневного обновления доступных дат
            current_day = date.today().day
            if current_day != last_update_day:
                await update_available_dates()
                last_update_day = current_day
            
            # Send day before reminders
            await send_day_before_reminders(notification_service)
            
            # Send hour before reminders
            await send_hour_before_reminders(notification_service)
            
            # Wait for next check (every 5 minutes)
            # More frequent checks reduce the chance of missing notifications
            await asyncio.sleep(300)  # 5 minutes
        except Exception as e:
            logger.error(f"Error in notification service: {e}")
            # Wait a bit before retrying
            await asyncio.sleep(60)

async def update_available_dates():
    """Обновляет доступные даты на ближайшие две недели"""
    try:
        logger.info("Updating available dates for the next two weeks...")
        result = await timeslot_service.update_available_dates()
        if result:
            logger.info("Available dates successfully updated")
            # Также удаляем устаревшие даты
            await timeslot_service.remove_old_available_dates()
        else:
            logger.error("Failed to update available dates")
    except Exception as e:
        logger.error(f"Error updating available dates: {e}")

async def send_day_before_reminders(notification_service):
    """Send reminders for meetings happening tomorrow"""
    logger.info("Checking for meetings tomorrow...")
    
    # Calculate tomorrow's date
    tomorrow = date.today() + timedelta(days=1)
    
    try:
        # Check if pool is initialized
        pool_obj = await get_pool()
        if pool_obj is None:
            logger.info("Database pool not initialized. Initializing...")
            await init_db()
            
        # Get all confirmed meetings for tomorrow
        async with pool_obj.acquire() as conn:
            meetings = await conn.fetch('''
                SELECT g.*, c.name as city_name
                FROM meetings g
                JOIN cities c ON g.city_id = c.id
                WHERE g.meeting_date = $1 AND g.status = $2
            ''', tomorrow, 'confirmed')
        
        for meeting in meetings:
            # Get all members
            members = await get_meeting_members(meeting['id'])
            
            # Send reminder to each member
            for member in members:
                await notification_service.send_day_before_reminder(
                    member['user_id'], meeting
                )
            
            logger.info(f"Sent day-before reminders for meeting {meeting['id']} to {len(members)} members")
    except Exception as e:
        logger.error(f"Error sending day-before reminders: {e}")

async def send_hour_before_reminders(notification_service):
    """Send reminders for meetings happening in the next hour"""
    logger.info("Checking for meetings in the next hour...")
    
    # Calculate current date and time
    now = datetime.now()
    current_date = now.date()
    current_time = now.time()
    
    # Calculate time range (next hour)
    hour_later = (datetime.combine(date.today(), current_time) + timedelta(hours=1)).time()
    
    try:
        # Check if pool is initialized
        pool_obj = await get_pool()
        if pool_obj is None:
            logger.info("Database pool not initialized. Initializing...")
            await init_db()
            
        # Get all confirmed meetings for today with times in the next hour
        async with pool_obj.acquire() as conn:
            meetings = await conn.fetch('''
                SELECT g.*, c.name as city_name
                FROM meetings g
                JOIN cities c ON g.city_id = c.id
                WHERE g.meeting_date = $1 AND g.status = $2
                AND g.meeting_time BETWEEN $3 AND $4
            ''', current_date, 'confirmed', current_time, hour_later)
        
        for meeting in meetings:
            # Check if we're within 15 minutes of the hour mark to avoid duplicate notifications
            meeting_datetime = datetime.combine(meeting['meeting_date'], meeting['meeting_time'])
            time_diff = (meeting_datetime - now).total_seconds() / 60
            
            # Expanded time window to reduce chance of missing notifications
            # Now checks if we're between 40 and 80 minutes before the meeting
            if 40 <= time_diff <= 80:  # Within 20 minutes of the hour mark
                # Get all members
                members = await get_meeting_members(meeting['id'])
                
                # Send reminder to each member
                for member in members:
                    await notification_service.send_hour_before_reminder(
                        member['user_id'], meeting
                    )
                
                logger.info(f"Sent hour-before reminders for meeting {meeting['id']} to {len(members)} members")
    except Exception as e:
        logger.error(f"Error sending hour-before reminders: {e}")