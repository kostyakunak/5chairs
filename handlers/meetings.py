import logging
from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, date, time, timedelta

from database.db import (
    get_user, get_pending_meetings_by_city, join_meeting, leave_meeting,
    get_meeting, get_meeting_participants, count_meeting_participants,
    create_meeting, get_users_by_city, get_user_meetings, update_meeting
)
from config import MIN_MEETING_PARTICIPANTS

# Define states for joining a meeting
class JoinMeetingStates(StatesGroup):
    confirm = State()

# Create router
router = Router()

# Join command handler
@router.message(Command("join"))
async def cmd_join(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Get user from database
    user = await get_user(user_id)
    
    if not user:
        await message.answer(
            "You are not registered yet. Please use /start to register."
        )
        return
    
    if not user['city']:
        await message.answer(
            "You need to set your city in your profile before joining meetings.\n"
            "Use /edit to update your profile."
        )
        return
    
    # Get pending meetings in user's city
    meetings = await get_pending_meetings_by_city(user['city'])
    
    if not meetings:
        # No meetings found, check if there are enough users to create one
        users_in_city = await get_users_by_city(user['city'])
        
        if len(users_in_city) < MIN_MEETING_PARTICIPANTS:
            await message.answer(
                f"There are no meetings in {user['city']} yet.\n\n"
                f"We need at least {MIN_MEETING_PARTICIPANTS} people in your city to form a meeting.\n"
                f"Currently there are {len(users_in_city)} people (including you) in {user['city']}.\n\n"
                f"You've been added to the waiting list. We'll notify you when a meeting is formed!"
            )
            return
        
        # Create a new meeting
        # Schedule it for next weekend at 18:00
        today = date.today()
        days_until_saturday = (5 - today.weekday()) % 7
        if days_until_saturday == 0:
            days_until_saturday = 7  # If today is Saturday, schedule for next Saturday
        
        meeting_date = today + timedelta(days=days_until_saturday)
        meeting_time = time(18, 0)  # 6:00 PM
        
        meeting_id = await create_meeting(
            location=user['city'],
            date=meeting_date,
            time=meeting_time
        )
        
        # Join the user to the meeting
        await join_meeting(user_id, meeting_id)
        
        await message.answer(
            f"A new meeting has been created in {user['city']} for {meeting_date.strftime('%A, %d.%m.%Y')} at {meeting_time.strftime('%H:%M')}.\n\n"
            f"You've been added as the first participant! We need {MIN_MEETING_PARTICIPANTS-1} more people to join.\n\n"
            f"We'll notify you when more people join the meeting."
        )
        return
    
    # Show available meetings
    builder = InlineKeyboardBuilder()
    
    for meeting in meetings:
        # Get participant count
        participant_count = await count_meeting_participants(meeting['id'])
        
        # Format button text
        meeting_text = (
            f"{meeting['date'].strftime('%d.%m.%Y')} at {meeting['time'].strftime('%H:%M')} "
            f"({participant_count}/{MIN_MEETING_PARTICIPANTS} participants)"
        )
        
        builder.add(InlineKeyboardButton(
            text=meeting_text,
            callback_data=f"join_{meeting['id']}"
        ))
    
    builder.adjust(1)  # One button per row
    
    await message.answer(
        f"Available meetings in {user['city']}:\n"
        f"Select a meeting to join:",
        reply_markup=builder.as_markup()
    )

# Join meeting callback handler
@router.callback_query(F.data.startswith("join_"))
async def process_join_callback(callback_query, state: FSMContext):
    user_id = callback_query.from_user.id
    meeting_id = int(callback_query.data.split("_")[1])
    
    # Get user and meeting
    user = await get_user(user_id)
    meeting = await get_meeting(meeting_id)
    
    if not meeting:
        await callback_query.message.answer("This meeting no longer exists.")
        await callback_query.answer()
        return
    
    # Join the meeting
    await join_meeting(user_id, meeting_id)
    
    # Get updated participant count
    participant_count = await count_meeting_participants(meeting_id)
    
    await callback_query.message.answer(
        f"You've joined the meeting in {meeting['location']} on {meeting['date'].strftime('%d.%m.%Y')} at {meeting['time'].strftime('%H:%M')}.\n\n"
        f"Current participants: {participant_count}/{MIN_MEETING_PARTICIPANTS}\n\n"
        f"We'll notify you when more people join the meeting."
    )
    
    # Check if meeting is now full
    if participant_count >= MIN_MEETING_PARTICIPANTS:
        # Get all participants
        participants = await get_meeting_participants(meeting_id)
        
        # Update meeting status to confirmed
        await update_meeting(meeting_id, status='confirmed')
        
        # Notify all participants that the meeting is confirmed
        for participant in participants:
            # For the current user, send the message directly
            if participant['id'] == user_id:
                await callback_query.message.answer(
                    f"🎉 Great news! The meeting in {meeting['location']} on {meeting['date'].strftime('%d.%m.%Y')} at {meeting['time'].strftime('%H:%M')} "
                    f"now has {participant_count} participants and is confirmed!\n\n"
                    f"We'll send you a reminder the day before the meeting."
                )
            # For other users, we would use the bot to send a message
            # In a real implementation, this would be handled by the notification service
            # Here we'll just log it
            else:
                logging.info(f"Would send confirmation to user {participant['id']} for meeting {meeting_id}")
                
                # In a real implementation, you would use something like:
                # await bot.send_message(
                #     participant['id'],
                #     f"🎉 Great news! The meeting in {meeting['location']} on {meeting['date'].strftime('%d.%m.%Y')} at {meeting['time'].strftime('%H:%M')} "
                #     f"now has {participant_count} participants and is confirmed!\n\n"
                #     f"We'll send you a reminder the day before the meeting."
                # )
    
    await callback_query.answer()

# Leave command handler
@router.message(Command("leave"))
async def cmd_leave(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Get user from database
    user = await get_user(user_id)
    
    if not user:
        await message.answer(
            "You are not registered yet. Please use /start to register."
        )
        return
    
    # Get user's meetings
    meetings = await get_user_meetings(user_id)
    
    if not meetings:
        await message.answer("You are not participating in any meetings.")
        return
    
    # Show meetings to leave
    builder = InlineKeyboardBuilder()
    
    for meeting in meetings:
        # Format button text
        meeting_text = f"{meeting['date'].strftime('%d.%m.%Y')} at {meeting['time'].strftime('%H:%M')} in {meeting['location']}"
        
        builder.add(InlineKeyboardButton(
            text=meeting_text,
            callback_data=f"leave_{meeting['id']}"
        ))
    
    builder.adjust(1)  # One button per row
    
    await message.answer(
        "Select a meeting to leave:",
        reply_markup=builder.as_markup()
    )

# Leave meeting callback handler
@router.callback_query(F.data.startswith("leave_"))
async def process_leave_callback(callback_query, state: FSMContext):
    user_id = callback_query.from_user.id
    meeting_id = int(callback_query.data.split("_")[1])
    
    # Get meeting
    meeting = await get_meeting(meeting_id)
    
    if not meeting:
        await callback_query.message.answer("This meeting no longer exists.")
        await callback_query.answer()
        return
    
    # Leave the meeting
    await leave_meeting(user_id, meeting_id)
    
    # Get updated participant count
    participant_count = await count_meeting_participants(meeting_id)
    
    await callback_query.message.answer(
        f"You've left the meeting in {meeting['location']} on {meeting['date'].strftime('%d.%m.%Y')} at {meeting['time'].strftime('%H:%M')}."
    )
    
    # Check if meeting now has too few participants
    if participant_count < MIN_MEETING_PARTICIPANTS and meeting['status'] == 'confirmed':
        # In a real bot, you would notify all remaining participants
        # Here we'll just simulate it for the current user
        await callback_query.message.answer(
            f"Note: The meeting now has fewer than {MIN_MEETING_PARTICIPANTS} participants and may be at risk of cancellation."
        )
    
    await callback_query.answer()

# Function to register handlers with the dispatcher
def register_meeting_handlers(dp):
    dp.include_router(router)