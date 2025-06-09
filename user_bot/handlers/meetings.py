from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta

from database.db import get_user, get_user_meetings, get_meeting_members, get_meeting, pool, remove_meeting_member

# Create router
router = Router()

# Function to register handlers with the dispatcher
def register_meetings_handlers(dp):
    dp.include_router(router)

@router.message(Command("my_meetings"))
async def cmd_meetings(message: Message):
    """Display user's meetings with time preference information"""
    user_id = message.from_user.id
    
    try:
        # Get user's meetings with time preference info
        meetings = await get_user_meetings(user_id)
        
        if not meetings or len(meetings) == 0:
            await message.answer("You don't have any meetings yet.")
            return
        
        # Group meetings by time
        now = datetime.now()
        upcoming_meetings = []
        past_meetings = []
        
        for meeting in meetings:
            meeting_datetime = datetime.combine(meeting['meeting_date'], meeting['meeting_time'])
            if meeting_datetime > now:
                upcoming_meetings.append(meeting)
            else:
                past_meetings.append(meeting)
        
        # Sort upcoming meetings by date
        upcoming_meetings.sort(key=lambda x: datetime.combine(x['meeting_date'], x['meeting_time']))
        
        # Create inline keyboard with meeting options
        if upcoming_meetings:
            meeting_text = "📋 Your upcoming meetings:\n\n"
            
            builder = InlineKeyboardBuilder()
            
            for i, meeting in enumerate(upcoming_meetings, 1):
                meeting_text += (
                    f"{i}. {meeting['name']}\n"
                    f"📍 {meeting['city_name']}\n"
                    f"⏰ {meeting['meeting_date'].strftime('%a, %d.%m.%Y')} at {meeting['meeting_time'].strftime('%H:%M')}\n"
                    f"📌 {meeting['venue']}\n\n"
                )
                
                builder.add(InlineKeyboardButton(
                    text=f"Details: {meeting['name']}",
                    callback_data=f"meeting_details_{meeting['id']}"
                ))
            
            builder.adjust(1)
            
            await message.answer(
                meeting_text,
                reply_markup=builder.as_markup()
            )
        else:
            await message.answer("You don't have any upcoming meetings.")
        
        # Show past meetings if any
        if past_meetings and len(past_meetings) > 0:
            past_text = "📜 Your past meetings:\n\n"
            
            # Sort past meetings by date, most recent first
            past_meetings.sort(key=lambda x: datetime.combine(x['meeting_date'], x['meeting_time']), reverse=True)
            
            # Only show the 3 most recent past meetings
            for i, meeting in enumerate(past_meetings[:3], 1):
                past_text += (
                    f"{i}. {meeting['name']}\n"
                    f"📍 {meeting['city_name']}\n"
                    f"⏰ {meeting['meeting_date'].strftime('%a, %d.%m.%Y')} at {meeting['meeting_time'].strftime('%H:%M')}\n\n"
                )
            
            if len(past_meetings) > 3:
                past_text += f"...and {len(past_meetings) - 3} more past meetings."
                
            await message.answer(past_text)
            
    except Exception as e:
        await message.answer(f"Error retrieving your meetings: {str(e)}")

# Meeting details handler
@router.callback_query(F.data.startswith("meeting_details_"))
async def show_meeting_details(callback, state: FSMContext):
    """Show detailed information about a specific meeting"""
    # Extract meeting ID
    meeting_id = int(callback.data.split("_")[2])
    
    try:
        # Get meeting details with time preference information
        async with pool.acquire() as conn:
            meeting = await conn.fetchrow('''
                SELECT m.*, c.name as city_name, ts.day_of_week, ts.start_time, ts.end_time
                FROM meetings m
                JOIN cities c ON m.city_id = c.id
                LEFT JOIN meeting_time_slots mts ON m.id = mts.meeting_id
                LEFT JOIN time_slots ts ON mts.time_slot_id = ts.id
                WHERE m.id = $1
            ''', meeting_id)
        
        if not meeting:
            await callback.message.edit_text("Meeting details not found.")
            return
        
        # Get meeting members
        members = await get_meeting_members(meeting_id)
        
        # Format meeting details
        details = (
            f"📅 Meeting: {meeting['name']}\n"
            f"📍 Location: {meeting['city_name']} - {meeting['venue']}"
        )
        
        # Add address if available
        if meeting.get('venue_address'):
            details += f"\n📌 Address: {meeting['venue_address']}"
        
        details += (
            f"\n⏰ Date & Time: {meeting['meeting_date'].strftime('%A, %d.%m.%Y')} at {meeting['meeting_time'].strftime('%H:%M')}\n"
            f"Status: {meeting['status'].capitalize()}\n"
        )
        
        # Add time preference if available
        if meeting.get('day_of_week') and meeting.get('start_time') and meeting.get('end_time'):
            details += f"\n⏱️ Time Preference: {meeting['day_of_week']} {meeting['start_time'].strftime('%H:%M')}-{meeting['end_time'].strftime('%H:%M')}"
        
        # Add countdown until meeting
        meeting_datetime = datetime.combine(meeting['meeting_date'], meeting['meeting_time'])
        now = datetime.now()
        
        if meeting_datetime > now:
            time_until = meeting_datetime - now
            days = time_until.days
            hours, remainder = divmod(time_until.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            
            details += f"\n\n⏳ Time until meeting: {days} days, {hours} hours, {minutes} minutes"
        
        # Add member information
        details += "\n\nParticipants:\n"
        
        if members:
            for i, member in enumerate(members, 1):
                details += f"{i}. {member['name']} {member['surname']}\n"
        else:
            details += "No participants yet."
        
        # Add agenda information
        details += (
            f"\n📋 Meeting Agenda:\n"
            f"- Introduction and ice-breakers (15 min)\n"
            f"- 5 Chairs method explanation (10 min)\n"
            f"- Main discussion (60 min)\n"
            f"- Wrap-up and next steps (15 min)\n\n"
            f"Please arrive 5-10 minutes early to get settled."
        )
        
        # Create back button
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(
            text="Back to Meetings List",
            callback_data="back_to_meetings"
        ))
        
        await callback.message.edit_text(
            details,
            reply_markup=builder.as_markup()
        )
        
    except Exception as e:
        await callback.message.edit_text(f"Error retrieving meeting details: {str(e)}")

# Back to meetings list handler
@router.callback_query(F.data == "back_to_meetings")
async def back_to_meetings(callback, state: FSMContext):
    """Return to meetings list"""
    # Call the meetings command handler with the callback message
    message = callback.message
    message.from_user = callback.from_user
    await cmd_meetings(message)

# Показываем список встреч пользователя
@router.message(Command("my_meetings"))
async def cmd_my_meetings(message: Message):
    user_id = message.from_user.id
    meetings = await get_user_meetings(user_id)
    if not meetings:
        await message.answer("У вас пока нет встреч.")
        return
    text = "Ваши встречи:\n"
    builder = InlineKeyboardBuilder()
    for m in meetings:
        text += f"\n{m['meeting_date'].strftime('%d.%m.%Y')} {m['meeting_time'].strftime('%H:%M')} — {m['city_name']} (id={m['id']})"
        builder.add(InlineKeyboardButton(
            text=f"Отменить встречу {m['id']}",
            callback_data=f"cancel_meeting_{m['id']}"
        ))
    builder.adjust(1)
    await message.answer(text, reply_markup=builder.as_markup())

# Подтверждение отмены встречи
@router.callback_query(F.data.startswith("cancel_meeting_"))
async def confirm_cancel_meeting(callback: CallbackQuery, state: FSMContext):
    meeting_id = int(callback.data.split("_")[-1])
    await callback.message.edit_text(
        f"Вы уверены, что хотите отменить участие во встрече id={meeting_id}?",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Да, выйти", callback_data=f"do_cancel_meeting_{meeting_id}"),
                 InlineKeyboardButton(text="Нет", callback_data="cancel_cancel_meeting")]
            ]
        )
    )

# Обработка подтверждения отмены
@router.callback_query(F.data.startswith("do_cancel_meeting_"))
async def do_cancel_meeting(callback: CallbackQuery, state: FSMContext):
    meeting_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    await remove_meeting_member(meeting_id, user_id)
    await callback.message.edit_text("Вы вышли из встречи.")
    # Показываем обновлённый список встреч
    meetings = await get_user_meetings(user_id)
    if not meetings:
        await callback.message.answer("У вас больше нет встреч.")
        return
    text = "Ваши встречи:\n"
    builder = InlineKeyboardBuilder()
    for m in meetings:
        text += f"\n{m['meeting_date'].strftime('%d.%m.%Y')} {m['meeting_time'].strftime('%H:%M')} — {m['city_name']} (id={m['id']})"
        builder.add(InlineKeyboardButton(
            text=f"Отменить встречу {m['id']}",
            callback_data=f"cancel_meeting_{m['id']}"
        ))
    builder.adjust(1)
    await callback.message.answer(text, reply_markup=builder.as_markup())

# Отмена отмены (оставить встречу)
@router.callback_query(F.data == "cancel_cancel_meeting")
async def cancel_cancel_meeting(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    meetings = await get_user_meetings(user_id)
    if not meetings:
        await callback.message.edit_text("У вас пока нет встреч.")
        return
    text = "Ваши встречи:\n"
    builder = InlineKeyboardBuilder()
    for m in meetings:
        text += f"\n{m['meeting_date'].strftime('%d.%m.%Y')} {m['meeting_time'].strftime('%H:%M')} — {m['city_name']} (id={m['id']})"
        builder.add(InlineKeyboardButton(
            text=f"Отменить встречу {m['id']}",
            callback_data=f"cancel_meeting_{m['id']}"
        ))
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup())