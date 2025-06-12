import logging
import asyncio
from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, date, time, timedelta
from aiogram.fsm.state import State
from typing import Optional

logger = logging.getLogger(__name__)

from database.db import (
    is_admin, create_meeting, get_meetings_by_status, get_meeting, update_meeting_status,
    get_active_cities, get_city, add_meeting_member, remove_meeting_member,
    get_meeting_members, count_meeting_members, get_user, pool, get_venues_by_city, get_venue,
    get_available_dates, get_available_date, update_available_date, get_available_dates_with_users_count,
    get_users_by_time_preference, get_compatible_users_for_meeting, create_meeting_from_available_date,
    get_pending_applications_by_timeslot
)
from config import MIN_MEETING_SIZE, MAX_MEETING_SIZE
from services.notification_service import NotificationService
from admin_bot.states import MeetingManagementStates

# Create router
router = Router()

# Meetings command handler
@router.message(Command("meetings"))
async def cmd_meetings(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Check if user is an admin
    if not await is_admin(user_id):
        await message.answer(
            "Sorry, you are not authorized to use this command."
        )
        return
    
    # Create meeting management keyboard
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Create Meeting"), KeyboardButton(text="Smart Meeting Creation")],
            [KeyboardButton(text="List Meetings")],
            [KeyboardButton(text="Back to Menu")]
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        "Meeting Management\n\n"
        "Here you can create and manage meetings.",
        reply_markup=keyboard
    )

# --- Восстановленная функция для извлечения meeting_id из callback_data ---
def extract_meeting_id_from_callback(callback_data):
    parts = callback_data.split('_')
    if callback_data.startswith("add_this_applicant_"):
        return int(parts[3])
    elif callback_data.startswith("members_meeting_"):
        return int(parts[-1])
    elif callback_data.startswith("manage_meeting_"):
        return int(parts[-1])
    elif callback_data.startswith("remove_member_"):
        return int(parts[2])
    elif callback_data.startswith("view_member_"):
        return int(parts[2])
    # fallback
    return int(parts[-1])

# --- Функции генерации и рендера названия встречи ---
def generate_meeting_name(city: str, venue: str, meeting_date: date) -> str:
    return f"{city}: {venue} {meeting_date.strftime('%d.%m.%Y')}"

def render_meeting_name(template: str, city: str, venue: str, meeting_date: date) -> str:
    return (template
            .replace("{city}", city)
            .replace("{venue}", venue)
            .replace("{date}", meeting_date.strftime('%d.%m.%Y')))

# Create meeting handler
@router.message(F.text == "Create Meeting")
async def create_meeting_command(message: Message, state: FSMContext):
    # Check if user is an admin
    if not await is_admin(message.from_user.id):
        return
    
    # Сбросить state
    await state.clear()

    # Начать с выбора города
    cities = await get_active_cities()
    if not cities:
        await message.answer("There are no active cities in the database.")
        return
    
    builder = InlineKeyboardBuilder()
    for city in cities:
        builder.add(InlineKeyboardButton(
            text=city['name'],
            callback_data=f"meeting_city_{city['id']}"
        ))
    builder.adjust(2)
    
    await message.answer(
        "Let's create a new meeting!\n\nPlease select the city for this meeting:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(MeetingManagementStates.create_city)

# Process meeting date
@router.message(MeetingManagementStates.create_date)
async def process_meeting_date(message: Message, state: FSMContext):
    date_str = message.text.strip()
    
    # Parse and validate date format using helper function
    from utils.helpers import parse_date
    
    meeting_date = parse_date(date_str)
    
    if not meeting_date:
        await message.answer(
            "Invalid date format. Please enter the date in format DD.MM.YYYY, YYYY-MM-DD, or DD/MM/YYYY:"
        )
        return
    
    # Check if date is in the future
    if meeting_date < date.today():
        await message.answer("Meeting date must be in the future. Please try again:")
        return
    
    # Save meeting date to state
    await state.update_data(meeting_date=meeting_date)
    
    await message.answer(
        "Please enter the meeting time in one of these formats:\n"
        "- HH:MM (e.g., 18:30)\n"
        "- HH.MM (e.g., 18.30)"
    )
    
    # Set state to wait for meeting time
    await state.set_state(MeetingManagementStates.create_time)

# Process meeting time
@router.message(MeetingManagementStates.create_time)
async def process_meeting_time(message: Message, state: FSMContext):
    time_str = message.text.strip()
    
    # Parse and validate time format using helper function
    from utils.helpers import parse_time
    
    meeting_time = parse_time(time_str)
    
    if not meeting_time:
        await message.answer(
            "Invalid time format. Please enter the time in 24-hour format (HH:MM or HH.MM):"
        )
        return
    
    # Save meeting time to state
    await state.update_data(meeting_time=meeting_time)
    
    # Get cities from database
    cities = await get_active_cities()
    
    if not cities:
        await message.answer("There are no active cities in the database.")
        await state.clear()
        return
    
    # Create city selection keyboard
    builder = InlineKeyboardBuilder()
    for city in cities:
        builder.add(InlineKeyboardButton(
            text=city['name'],
            callback_data=f"meeting_city_{city['id']}"
        ))
    builder.adjust(2)
    
    await message.answer(
        "Please select the city for this meeting:",
        reply_markup=builder.as_markup()
    )
    
    # Set state to wait for city selection
    await state.set_state(MeetingManagementStates.create_city)

# City selection handler
@router.callback_query(MeetingManagementStates.create_city, F.data.startswith("meeting_city_"))
async def process_city_selection(callback: CallbackQuery, state: FSMContext):
    city_id = int(callback.data.split("_")[-1])
    await state.update_data(city_id=city_id)
    city = await get_city(city_id)
    # Получаем уникальные даты для города
    async with pool.acquire() as conn:
        dates = await conn.fetch('''
            SELECT DISTINCT ad.date
            FROM available_dates ad
            JOIN time_slots ts ON ad.time_slot_id = ts.id
            WHERE ts.city_id = $1 AND ad.is_available = true
            ORDER BY ad.date
        ''', city_id)
    if not dates:
        await callback.message.edit_text("Нет доступных дат для этого города.")
        return
    builder = InlineKeyboardBuilder()
    for d in dates:
        day_of_week = d['date'].strftime('%A')
        builder.add(InlineKeyboardButton(
            text=f"{d['date'].strftime('%d.%m.%Y')} ({day_of_week})",
            callback_data=f"meeting_date_{d['date'].strftime('%Y-%m-%d')}"
        ))
    builder.adjust(2)
    await callback.message.edit_text(
        f"Выбран город: {city['name']}\n\nВыберите дату для встречи:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(MeetingManagementStates.create_date)

# Process meeting date
@router.callback_query(MeetingManagementStates.create_date, F.data.startswith("meeting_date_"))
async def process_meeting_date_selection(callback: CallbackQuery, state: FSMContext):
    date_str = callback.data.split("_")[-1]
    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    await state.update_data(meeting_date=date_obj)
    data = await state.get_data()
    city_id = data['city_id']
    # Получаем все таймслоты для этой даты и города
    async with pool.acquire() as conn:
        slots = await conn.fetch('''
            SELECT ts.id, ts.start_time, ts.end_time
            FROM available_dates ad
            JOIN time_slots ts ON ad.time_slot_id = ts.id
            WHERE ad.date = $1 AND ts.city_id = $2 AND ad.is_available = true
            ORDER BY ts.start_time
        ''', date_obj, city_id)
    if not slots:
        await callback.message.edit_text("Нет таймслотов для выбранной даты.")
        return
    builder = InlineKeyboardBuilder()
    for ts in slots:
        builder.add(InlineKeyboardButton(
            text=f"{ts['start_time'].strftime('%H:%M')}-{ts['end_time'].strftime('%H:%M')}",
            callback_data=f"meeting_timeslot_{ts['id']}"
        ))
    builder.adjust(1)
    await callback.message.edit_text("Выберите таймслот для встречи:", reply_markup=builder.as_markup())
    await state.set_state(MeetingManagementStates.create_time)

# Process meeting time
@router.callback_query(MeetingManagementStates.create_time, F.data.startswith("meeting_timeslot_"))
async def process_meeting_timeslot_selection(callback: CallbackQuery, state: FSMContext):
    time_slot_id = int(callback.data.split("_")[-1])
    await state.update_data(time_slot_id=time_slot_id)
    # Получаем start_time выбранного таймслота
    async with pool.acquire() as conn:
        ts = await conn.fetchrow('SELECT start_time FROM time_slots WHERE id = $1', time_slot_id)
    if not ts:
        await callback.message.edit_text("Ошибка: таймслот не найден.")
        return
    await state.update_data(meeting_time=ts['start_time'])
    data = await state.get_data()
    city_id = data['city_id']
    city = await get_city(city_id)
    # Получаем venues для города
    venues = await get_venues_by_city(city_id)
    if not venues:
        await callback.message.edit_text(
            f"Выбран город: {city['name']}\n\nНет сохранённых площадок. Введите площадку вручную:")
        await state.set_state(MeetingManagementStates.create_venue)
        return
    builder = InlineKeyboardBuilder()
    for venue in venues:
        builder.add(InlineKeyboardButton(
            text=venue['name'],
            callback_data=f"meeting_venue_{venue['id']}"
        ))
    builder.add(InlineKeyboardButton(
        text="Ввести вручную",
        callback_data="meeting_venue_custom"
    ))
    builder.adjust(2)
    await callback.message.edit_text(
        f"Выберите площадку для встречи:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(MeetingManagementStates.create_venue)

# Process venue selection from callback
@router.callback_query(MeetingManagementStates.create_venue, F.data.startswith("meeting_venue_"))
async def process_venue_selection(callback: CallbackQuery, state: FSMContext):
    venue_data = callback.data.split("_")[-1]
    if venue_data == "custom":
        await callback.message.edit_text(
            "Пожалуйста, введите площадку для этой встречи:")
        return
    venue_id = int(venue_data)
    venue = await get_venue(venue_id)
    if not venue:
        await callback.message.edit_text("Площадка не найдена. Попробуйте ещё раз или введите вручную.")
        return
    await state.update_data(venue=venue['name'], venue_address=venue['address'], venue_id=venue_id)
    data = await state.get_data()
    city = await get_city(data['city_id'])
    meeting_date = data['meeting_date']
    meeting_time = data.get('meeting_time')
    if not meeting_time:
        await callback.message.edit_text("Ошибка: не удалось определить время встречи. Попробуйте выбрать таймслот заново.")
        return
    meeting_name = f"{city['name']}: {venue['name']} {meeting_date.strftime('%d.%m.%Y')}"
    await state.update_data(meeting_name=meeting_name)
    meeting_id = await create_meeting(
        name=meeting_name,
        meeting_date=meeting_date,
        meeting_time=meeting_time,
        city_id=data['city_id'],
        venue=venue['name'],
        created_by=callback.from_user.id,
        venue_address=venue['address']
    )
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            # ...
        ],
        resize_keyboard=True
    )
    await callback.message.answer(
        f"Встреча '{meeting_name}' успешно создана!\n\nХотите добавить участников сейчас?",
        reply_markup=keyboard
    )
    await state.update_data(meeting_id=meeting_id)
    await state.set_state(MeetingManagementStates.add_members)

# Smart Meeting Creation handler
@router.message(F.text == "Smart Meeting Creation")
async def smart_meeting_creation(message: Message, state: FSMContext):
    # Check if user is an admin
    if not await is_admin(message.from_user.id):
        return
    
    # Clear any previous state
    await state.clear()

    # Get active cities
    cities = await get_active_cities()
    if not cities:
        await message.answer("There are no active cities in the database.")
        return
    
    # Create city selection keyboard
    builder = InlineKeyboardBuilder()
    for city in cities:
        builder.add(InlineKeyboardButton(
            text=city['name'],
            callback_data=f"smart_meeting_city_{city['id']}"
        ))
    builder.adjust(2)
    
    await message.answer(
        "Smart Meeting Creation\n\n"
        "First, please select a city for the meeting:",
        reply_markup=builder.as_markup()
    )
    
    # Set state to wait for city selection
    await state.set_state(MeetingManagementStates.select_available_date)

# List meetings handler (теперь показывает выбор города)
@router.message(F.text == "List Meetings")
async def list_meetings(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    cities = await get_active_cities()
    if not cities:
        await message.answer("Нет активных городов.")
        return
    builder = InlineKeyboardBuilder()
    for city in cities:
        builder.add(InlineKeyboardButton(
            text=city['name'],
            callback_data=f"list_meetings_city_{city['id']}"
        ))
    builder.adjust(2)
    await message.answer(
        "Выберите город для просмотра встреч:",
        reply_markup=builder.as_markup()
    )
    await state.clear()

# Callback-обработчик выбора города для просмотра встреч
@router.callback_query(F.data.startswith("list_meetings_city_"))
async def list_meetings_for_city(callback: CallbackQuery, state: FSMContext):
    city_id = int(callback.data.split("_")[-1])
    await state.update_data(city_id=city_id)  # Сохраняем выбранный город в FSM
    # Получаем встречи этого города с разными статусами
    async with pool.acquire() as conn:
        meetings = await conn.fetch('''
            SELECT m.*, c.name as city_name
            FROM meetings m
            JOIN cities c ON m.city_id = c.id
            WHERE m.city_id = $1
            ORDER BY m.id
        ''', city_id)
    if not meetings:
        await callback.message.edit_text("В этом городе нет созданных встреч.")
        await state.clear()
        return
    builder = InlineKeyboardBuilder()
    for meeting in meetings:
        member_count = await count_meeting_members(meeting['id'])
        if member_count <= MAX_MEETING_SIZE:
            dots = '🔴' * member_count + '🟢' * (MAX_MEETING_SIZE - member_count)
        else:
            dots = '🔴' * MAX_MEETING_SIZE + f'+{member_count - MAX_MEETING_SIZE}'
        builder.add(InlineKeyboardButton(
            text=f"{dots} {meeting['meeting_time'].strftime('%H:%M')} {meeting['meeting_date'].strftime('%d.%m.%Y')}",
            callback_data=f"manage_meeting_{meeting['id']}"
        ))
    builder.adjust(1)
    await callback.message.edit_text(
        f"Список встреч в городе: {meetings[0]['city_name']}\n\nВыберите встречу для управления:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(MeetingManagementStates.select_meeting_to_manage)

# === ВОССТАНОВЛЕННЫЕ ОБРАБОТЧИКИ ДЛЯ ИЗМЕНЕНИЯ ДАТЫ/ВРЕМЕНИ ===

# Изменение даты встречи — показать список доступных дат
@router.callback_query(F.data.startswith("edit_meeting_date_"))
async def edit_meeting_date_select(callback: CallbackQuery, state: FSMContext):
    logger.warning(f"[DEBUG] edit_meeting_date_select: callback.data={callback.data}")
    meeting_id = int(callback.data.split('_')[-1])
    data = await get_meeting(meeting_id)
    city_id = data['city_id']
    # Получаем все доступные даты и таймслоты для города
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT ad.id as ad_id, ad.date, ts.id as ts_id, ts.start_time, ts.end_time
            FROM available_dates ad
            JOIN time_slots ts ON ad.time_slot_id = ts.id
            WHERE ts.city_id = $1 AND ad.is_available = true
            ORDER BY ad.date, ts.start_time
        ''', city_id)
    if not rows:
        await callback.message.edit_text("Нет доступных дат для этого города.")
        return
    # Собираем только уникальные даты
    unique_dates = []
    seen = set()
    for r in rows:
        date_obj = r['date']
        if date_obj not in seen:
            unique_dates.append(date_obj)
            seen.add(date_obj)
    builder = InlineKeyboardBuilder()
    for d in unique_dates:
        builder.add(InlineKeyboardButton(
            text=d.strftime('%d.%m.%Y'),
            callback_data=f"edit_meeting_select_date_{meeting_id}_{d.strftime('%Y-%m-%d')}"
        ))
    builder.add(InlineKeyboardButton(
        text="Назад",
        callback_data=f"manage_meeting_{meeting_id}"
    ))
    builder.adjust(2)
    await callback.message.edit_text("Выберите новую дату для встречи:", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("edit_meeting_select_date_"))
async def edit_meeting_select_date(callback: CallbackQuery, state: FSMContext):
    logger.warning(f"[DEBUG] edit_meeting_select_date: callback.data={callback.data}")
    parts = callback.data.split('_')
    meeting_id = int(parts[4])
    date_str = parts[5]
    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    meeting = await get_meeting(meeting_id)
    city_id = meeting['city_id']
    current_time = meeting['meeting_time']
    # Получаем все таймслоты для этой даты и города
    async with pool.acquire() as conn:
        slots = await conn.fetch('''
            SELECT ts.id, ts.start_time, ts.end_time
            FROM available_dates ad
            JOIN time_slots ts ON ad.time_slot_id = ts.id
            WHERE ad.date = $1 AND ts.city_id = $2 AND ad.is_available = true
            ORDER BY ts.start_time
        ''', date_obj, city_id)
    if not slots:
        await callback.message.edit_text("Нет таймслотов для выбранной даты.")
        return
    builder = InlineKeyboardBuilder()
    for ts in slots:
        # Не показываем текущий таймслот встречи
        if date_obj == meeting['meeting_date'] and ts['start_time'] == current_time:
            continue
        builder.add(InlineKeyboardButton(
            text=f"{ts['start_time'].strftime('%H:%M')}-{ts['end_time'].strftime('%H:%M')}",
            callback_data=f"edit_meeting_select_timeslot_{meeting_id}_{date_str}_{ts['id']}"
        ))
    builder.add(InlineKeyboardButton(
        text="Назад",
        callback_data=f"edit_meeting_date_{meeting_id}"
    ))
    builder.adjust(1)
    await callback.message.edit_text("Выберите таймслот для новой даты:", reply_markup=builder.as_markup())

# --- Исправленный обработчик выбора таймслота для новой даты ---
@router.callback_query(F.data.startswith("edit_meeting_select_timeslot_"))
async def edit_meeting_select_timeslot(callback: CallbackQuery, state: FSMContext):
    logger.warning(f"[DEBUG] edit_meeting_select_timeslot: callback.data={callback.data}")
    parts = callback.data.split("_")
    meeting_id = int(parts[4])
    date_str = parts[5]
    time_slot_id = int(parts[6])
    logger.warning(f"[DEBUG] edit_meeting_select_timeslot: meeting_id={meeting_id}, date_str={date_str}, time_slot_id={time_slot_id}")
    new_date = datetime.strptime(date_str, "%Y-%m-%d").date()

    # Получаем start_time для выбранного таймслота
    async with pool.acquire() as conn:
        ts = await conn.fetchrow('SELECT start_time FROM time_slots WHERE id = $1', time_slot_id)
    logger.warning(f"[DEBUG] edit_meeting_select_timeslot: ts={ts}")
    if not ts:
        logger.error(f"[ERROR] Таймслот не найден: id={time_slot_id}")
        await callback.message.edit_text("Ошибка: таймслот не найден.")
        return
    new_time = ts['start_time']

    # Обновляем дату и время встречи
    async with pool.acquire() as conn:
        result1 = await conn.execute('''
            UPDATE meetings SET meeting_date = $1, meeting_time = $2 WHERE id = $3
        ''', new_date, new_time, meeting_id)
        logger.warning(f"[DEBUG] UPDATE meetings result: {result1}")
        result2 = await conn.execute('''
            UPDATE meeting_time_slots SET time_slot_id = $1 WHERE meeting_id = $2
        ''', time_slot_id, meeting_id)
        logger.warning(f"[DEBUG] UPDATE meeting_time_slots result: {result2}")

    await callback.message.edit_text("Дата и время встречи успешно обновлены!")
    logger.warning(f"[DEBUG] edit_meeting_select_timeslot: возвращаемся в меню управления встречей для meeting_id={meeting_id}")
    await process_meeting_selection(callback, state, meeting_id=meeting_id)

# --- Исправленный process_meeting_selection ---
@router.callback_query(F.data.startswith("manage_meeting_"))
async def process_meeting_selection(callback: CallbackQuery, state: FSMContext, meeting_id: Optional[int] = None):
    logger.warning(f"[DEBUG] process_meeting_selection: callback.data={callback.data}")
    if meeting_id is None:
        meeting_id = int(callback.data.split('_')[-1])
    data = await state.get_data()
    city_id = data.get('city_id')
    logger.warning(f"[DEBUG] process_meeting_selection: meeting_id={meeting_id}, city_id={city_id}")
    await state.update_data(meeting_id=meeting_id)
    meeting = await get_meeting(meeting_id)
    logger.warning(f"[DEBUG] process_meeting_selection: meeting={meeting}")
    if not meeting:
        logger.error(f"[ERROR] Встреча не найдена: id={meeting_id}")
        await callback.message.edit_text("Встреча не найдена.")
        return
    # Формируем меню управления встречей
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="Участники",
        callback_data=f"members_meeting_{meeting_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="Изменить дату",
        callback_data=f"edit_meeting_date_{meeting_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="Изменить время",
        callback_data=f"edit_meeting_time_{meeting_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="Удалить встречу",
        callback_data=f"del_{meeting_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="Назад к списку встреч",
        callback_data=f"list_meetings_city_{city_id}"
    ))
    builder.adjust(1)
    text = (
        f"<b>Управление встречей</b>\n"
        f"Название: {meeting['name']}\n"
        f"Дата: {meeting['meeting_date'].strftime('%d.%m.%Y')}\n"
        f"Время: {meeting['meeting_time'].strftime('%H:%M')}\n"
        f"Площадка: {meeting['venue']}\n"
        f"Статус: {meeting['status']}\n"
    )
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await state.set_state(MeetingManagementStates.select_meeting_to_manage)

# Callback-обработчик выбора города для умного создания встречи
@router.callback_query(MeetingManagementStates.select_available_date, F.data.startswith("smart_meeting_city_"))
async def smart_meeting_city_selected(callback: CallbackQuery, state: FSMContext):
    city_id = int(callback.data.split("_")[-1])
    await state.update_data(city_id=city_id)
    city = await get_city(city_id)
    # Получаем все доступные даты для города
    async with pool.acquire() as conn:
        dates = await conn.fetch('''
            SELECT DISTINCT ad.date
            FROM available_dates ad
            JOIN time_slots ts ON ad.time_slot_id = ts.id
            WHERE ts.city_id = $1 AND ad.is_available = true
            ORDER BY ad.date
        ''', city_id)
    if not dates:
        await callback.message.edit_text(f"Нет доступных дат для {city['name']}.")
        return
    # Собираем только уникальные даты
    unique_dates = []
    seen = set()
    for d in dates:
        date_obj = d['date']
        if date_obj not in seen:
            unique_dates.append(date_obj)
            seen.add(date_obj)
    builder = InlineKeyboardBuilder()
    for date_obj in unique_dates:
        day_of_week = date_obj.strftime('%A')
        builder.add(InlineKeyboardButton(
            text=f"{date_obj.strftime('%d.%m.%Y')} ({day_of_week})",
            callback_data=f"smart_meeting_date_{date_obj.strftime('%Y-%m-%d')}"
        ))
    builder.add(InlineKeyboardButton(
        text="Cancel",
        callback_data="cancel_smart_meeting"
    ))
    builder.adjust(2)
    await callback.message.edit_text(
        f"Выбран город: {city['name']}\n\nВыберите дату для встречи:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(MeetingManagementStates.smart_meeting_date)

# Новый обработчик: выбор таймслота после выбора даты
@router.callback_query(MeetingManagementStates.smart_meeting_date, F.data.startswith("smart_meeting_date_"))
async def smart_meeting_date_selected(callback: CallbackQuery, state: FSMContext):
    date_str = callback.data.split("_")[-1]
    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    await state.update_data(meeting_date=date_obj)
    data = await state.get_data()
    city_id = data['city_id']
    # Получаем все таймслоты для этой даты и города
    async with pool.acquire() as conn:
        slots = await conn.fetch('''
            SELECT ts.id, ts.start_time, ts.end_time
            FROM available_dates ad
            JOIN time_slots ts ON ad.time_slot_id = ts.id
            WHERE ad.date = $1 AND ts.city_id = $2 AND ad.is_available = true
            ORDER BY ts.start_time
        ''', date_obj, city_id)
    if not slots:
        await callback.message.edit_text("Нет таймслотов для выбранной даты.")
        return
    builder = InlineKeyboardBuilder()
    for ts in slots:
        builder.add(InlineKeyboardButton(
            text=f"{ts['start_time'].strftime('%H:%M')}-{ts['end_time'].strftime('%H:%M')}",
            callback_data=f"smart_meeting_timeslot_{ts['id']}"
        ))
    builder.add(InlineKeyboardButton(
        text="Назад",
        callback_data=f"smart_meeting_city_{city_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="Cancel",
        callback_data="cancel_smart_meeting"
    ))
    builder.adjust(1)
    await callback.message.edit_text("Выберите таймслот для встречи:", reply_markup=builder.as_markup())
    await state.set_state(MeetingManagementStates.smart_meeting_timeslot)

# 3. После выбора таймслота — сохраняем meeting_time (start_time) и переходим к выбору venue
@router.callback_query(MeetingManagementStates.smart_meeting_timeslot, F.data.startswith("smart_meeting_timeslot_"))
async def smart_meeting_timeslot_selected(callback: CallbackQuery, state: FSMContext):
    time_slot_id = int(callback.data.split("_")[-1])
    await state.update_data(time_slot_id=time_slot_id)
    # Получаем start_time выбранного таймслота
    async with pool.acquire() as conn:
        ts = await conn.fetchrow('SELECT start_time FROM time_slots WHERE id = $1', time_slot_id)
    if not ts:
        await callback.message.edit_text("Ошибка: таймслот не найден.")
        return
    await state.update_data(meeting_time=ts['start_time'])
    data = await state.get_data()
    city_id = data['city_id']
    city = await get_city(city_id)
    # Получаем venues для города
    venues = await get_venues_by_city(city_id)
    if not venues:
        await callback.message.edit_text(
            f"Выбран город: {city['name']}\n\nНет сохранённых площадок. Введите площадку вручную:")
        await state.set_state(MeetingManagementStates.smart_meeting_venue)
        return
    builder = InlineKeyboardBuilder()
    for venue in venues:
        builder.add(InlineKeyboardButton(
            text=venue['name'],
            callback_data=f"smart_meeting_venue_{venue['id']}"
        ))
    builder.add(InlineKeyboardButton(
        text="Ввести вручную",
        callback_data="smart_meeting_venue_custom"
    ))
    builder.adjust(2)
    await callback.message.edit_text(
        f"Выберите площадку для встречи:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(MeetingManagementStates.smart_meeting_venue)

# --- Smart Meeting Creation: выбор площадки из списка или вручную ---
@router.callback_query(MeetingManagementStates.smart_meeting_venue, F.data.startswith("smart_meeting_venue_"))
async def smart_meeting_venue_selected(callback: CallbackQuery, state: FSMContext):
    venue_data = callback.data.split("_")[-1]
    if venue_data == "custom":
        await callback.message.edit_text("Пожалуйста, введите площадку для этой встречи:")
        await state.set_state(MeetingManagementStates.smart_meeting_venue_manual)
        return
    venue_id = int(venue_data)
    venue = await get_venue(venue_id)
    if not venue:
        await callback.message.edit_text("Площадка не найдена. Попробуйте ещё раз или введите вручную.")
        return
    await state.update_data(venue=venue['name'], venue_address=venue['address'], venue_id=venue_id)
    await continue_smart_meeting_after_venue(callback.message, state)

# --- Smart Meeting Creation: обработка ручного ввода площадки ---
@router.message(MeetingManagementStates.smart_meeting_venue_manual)
async def smart_meeting_venue_manual_input(message: Message, state: FSMContext):
    venue_name = message.text.strip()
    if not venue_name:
        await message.answer("Название площадки не может быть пустым. Введите ещё раз:")
        return
    await state.update_data(venue=venue_name, venue_address="")
    await continue_smart_meeting_after_venue(message, state)

# --- Универсальная функция для продолжения flow после выбора площадки ---
async def continue_smart_meeting_after_venue(msg_obj, state: FSMContext):
    data = await state.get_data()
    city_id = data['city_id']
    meeting_date = data.get('meeting_date')
    meeting_time = data.get('meeting_time')
    venue = data.get('venue')
    if not meeting_date or not meeting_time or not venue:
        await msg_obj.answer("Ошибка: не хватает данных для создания встречи. Попробуйте выбрать дату и таймслот заново.")
        return
    meeting_name = f"{(await get_city(city_id))['name']}: {venue} {meeting_date.strftime('%d.%m.%Y')}"
    await state.update_data(meeting_name=meeting_name)
    # --- Получаем time_slot_id ---
    async with pool.acquire() as conn:
        slot_row = await conn.fetchrow('''
            SELECT ts.id
            FROM available_dates ad
            JOIN time_slots ts ON ad.time_slot_id = ts.id
            WHERE ad.date = $1 AND ts.start_time = $2 AND ts.city_id = $3
        ''', meeting_date, meeting_time, city_id)
        if not slot_row:
            await msg_obj.answer("Не удалось определить таймслот для этой встречи.")
        return
        time_slot_id = slot_row['id']
    await state.update_data(time_slot_id=time_slot_id)
    # --- Получаем аппликантов ---
    city = await get_city(city_id)
    async with pool.acquire() as conn:
        applicants = await get_pending_applications_by_timeslot(city_id, time_slot_id)
    if not applicants:
        await msg_obj.answer("Нет подходящих аппликантов для этой встречи.")
        return
    user_ids = [a['user_id'] for a in applicants]
    smart_selected = data.get('smart_selected_users', []) if data else []
    await state.update_data(smart_applicants=user_ids)
    # Показываем список пользователей
    builder = InlineKeyboardBuilder()
    for a in applicants:
        is_selected = a['user_id'] in smart_selected
        check = '✅ ' if is_selected else ''
        builder.add(InlineKeyboardButton(
            text=f"{check}{a['user_name']} (@{a['user_username'] or '-'}), {a['user_age']}",
            callback_data=f"smart_view_user_{a['user_id']}"
        ))
    builder.add(InlineKeyboardButton(
        text="Подтвердить создание встречи",
        callback_data="smart_confirm_creation"
    ))
    builder.add(InlineKeyboardButton(
        text="Назад",
        callback_data="cancel_smart_meeting"
    ))
    builder.adjust(1)
    await msg_obj.answer(
        "Выберите участников для встречи:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(MeetingManagementStates.smart_select_users)

# --- Smart Meeting Creation: просмотр профиля кандидата ---
# Этот обработчик обязателен для корректной работы smart режима!
@router.callback_query(MeetingManagementStates.smart_select_users, F.data.startswith("smart_"))
async def smart_profile_action(callback: CallbackQuery, state: FSMContext):
    if callback.data == "smart_confirm_creation":
        await smart_confirm_creation(callback, state)
        return
    data = await state.get_data()
    parts = callback.data.split("_")
    action = "_".join(parts[1:-1])
    user_id = int(parts[-1]) if parts[-1].isdigit() else None
    smart_selected = data.get('smart_selected_users', [])
    if action == "view_user":
        await show_applicant_profile(callback, 0, user_id, None, None, state)
        return
    if action == "add_user":
        if user_id not in smart_selected:
            smart_selected.append(user_id)
            await state.update_data(smart_selected_users=smart_selected)
        await callback.answer("Пользователь добавлен в список!")
        await show_applicant_profile(callback, 0, user_id, None, None, state)
    elif action == "remove_user":
        if user_id in smart_selected:
            smart_selected.remove(user_id)
            await state.update_data(smart_selected_users=smart_selected)
        await callback.answer("Пользователь удалён из списка!")
        await show_applicant_profile(callback, 0, user_id, None, None, state)
    elif action == "approve_user":
        async with pool.acquire() as conn:
            await conn.execute('UPDATE users SET status = $1 WHERE id = $2', 'approved', user_id)
        await callback.answer("Пользователь одобрен!")
        await show_applicant_profile(callback, 0, user_id, None, None, state)
    elif callback.data.startswith("smart_reject_confirm_"):
        # Подтверждение отклонения
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(
            text="Да, отклонить",
            callback_data=f"smart_reject_user_{user_id}"
        ))
        builder.add(InlineKeyboardButton(
            text="Нет, отмена",
            callback_data=f"smart_view_user_{user_id}"
        ))
        await callback.message.edit_text(
            "Вы уверены, что хотите отклонить пользователя?",
            reply_markup=builder.as_markup()
        )
    elif action == "reject_user":
        async with pool.acquire() as conn:
            await conn.execute('UPDATE users SET status = $1 WHERE id = $2', 'rejected', user_id)
        await callback.answer("Пользователь не прошел проверку!")
        # Показываем меню с кнопками вернуть/назад
        await show_applicant_profile(callback, 0, user_id, None, None, state)
    elif action == "restore_user":
        async with pool.acquire() as conn:
            await conn.execute('UPDATE users SET status = $1 WHERE id = $2', 'registered', user_id)
        await callback.answer("Пользователь восстановлен!")
        await show_applicant_profile(callback, 0, user_id, None, None, state)
    elif callback.data == "smart_back_to_list":
        # Возвращаем к списку кандидатов (повторно вызываем continue_smart_meeting_after_venue)
        await continue_smart_meeting_after_venue(callback.message, state)
    else:
        await callback.answer("Действие не распознано.")

# === DEBUG ОБРАБОТЧИК ДЛЯ ВСЕХ CALLBACK_QUERY ===
# Временно отключён для корректной работы основных обработчиков
# @router.callback_query()
# async def debug_all_callbacks(callback: CallbackQuery, state: FSMContext):
#     import logging
#     logger = logging.getLogger(__name__)
#     data = await state.get_data()
#     fsm_state = await state.get_state()
#     print(f"[DEBUG] Пойман callback: {callback.data}")
#     print(f"[DEBUG] Текущее состояние FSM: {fsm_state}")
#     print(f"[DEBUG] Данные FSM: {data}")
#     logger.warning(f"Пойман callback: {callback.data}")
#     logger.warning(f"FSM: {fsm_state}")
#     logger.warning(f"FSM data: {data}")
#     await callback.answer(f"DEBUG: {callback.data}", show_alert=True)

# Function to register handlers with the dispatcher
def register_meetings_handlers(dp):
    dp.include_router(router)

async def back_to_meetings_city(callback: CallbackQuery, state: FSMContext):
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"[DEBUG] back_to_meetings_city: вызван с callback.data={callback.data}")
    data = await state.get_data()
    logger.warning(f"[DEBUG] back_to_meetings_city: FSM data={data}")
    city_id = data.get('city_id')
    logger.warning(f"[DEBUG] back_to_meetings_city: city_id={city_id}")
    if not city_id:
        await callback.message.edit_text("Не удалось определить город для возврата к списку встреч.")
        return
    # Получаем встречи этого города с разными статусами
    async with pool.acquire() as conn:
        meetings = await conn.fetch('''
            SELECT m.*, c.name as city_name
            FROM meetings m
            JOIN cities c ON m.city_id = c.id
            WHERE m.city_id = $1
            ORDER BY m.id
        ''', city_id)
    logger.warning(f"[DEBUG] back_to_meetings_city: найдено встреч: {len(meetings)}")
    if not meetings:
        await callback.message.edit_text("В этом городе нет созданных встреч.")
        await state.clear()
        return
    builder = InlineKeyboardBuilder()
    for meeting in meetings:
        member_count = await count_meeting_members(meeting['id'])
        if member_count <= MAX_MEETING_SIZE:
            dots = '🔴' * member_count + '🟢' * (MAX_MEETING_SIZE - member_count)
        else:
            dots = '🔴' * MAX_MEETING_SIZE + f'+{member_count - MAX_MEETING_SIZE}'
        builder.add(InlineKeyboardButton(
            text=f"{dots} {meeting['meeting_time'].strftime('%H:%M')} {meeting['meeting_date'].strftime('%d.%m.%Y')}",
            callback_data=f"manage_meeting_{meeting['id']}"
        ))
    builder.adjust(1)
    await callback.message.edit_text(
        f"Список встреч в городе: {meetings[0]['city_name']}\n\nВыберите встречу для управления:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(MeetingManagementStates.select_meeting_to_manage)

@router.message(F.text == "Back to Meetings")
async def back_to_meetings(message: Message, state: FSMContext):
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"[DEBUG] back_to_meetings (reply keyboard): вызван пользователем {message.from_user.id}")
    cities = await get_active_cities()
    if not cities:
        await message.answer("Нет активных городов.")
        return
    builder = InlineKeyboardBuilder()
    for city in cities:
        builder.add(InlineKeyboardButton(
            text=city['name'],
            callback_data=f"list_meetings_city_{city['id']}"
        ))
    builder.adjust(2)
    await message.answer(
        "Выберите город для просмотра встреч:",
        reply_markup=builder.as_markup()
    )
    await state.clear()

@router.callback_query(F.data == "cancel_smart_meeting")
async def cancel_smart_meeting(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "Создание встречи отменено."
    )
    # Здесь можно вызвать функцию показа главного меню, если нужно

@router.callback_query(F.data == "smart_confirm_creation")
async def smart_confirm_creation(callback: CallbackQuery, state: FSMContext):
    import logging
    logger = logging.getLogger(__name__)
    print("[DEBUG] smart_confirm_creation handler called!")
    logger.warning("[DEBUG] smart_confirm_creation handler called!")
    data = await state.get_data()
    selected = data.get('smart_selected_users', [])
    if not selected:
        await callback.message.answer("Выберите хотя бы одного участника для создания встречи.")
        return
    city_id = data['city_id']
    meeting_date = data['meeting_date']
    meeting_time = data['meeting_time']
    venue = data['venue']
    venue_address = data.get('venue_address', "")
    meeting_name = data['meeting_name']
    # Создаём встречу
    meeting_id = await create_meeting(
        name=meeting_name,
        meeting_date=meeting_date,
        meeting_time=meeting_time,
        city_id=city_id,
        venue=venue,
        created_by=callback.from_user.id,
        venue_address=venue_address
    )
    # Добавляем участников и подтверждаем заявки
    async with pool.acquire() as conn:
        for user_id in selected:
            # Если заявка была pending — одобряем
            await conn.execute('''
                UPDATE applications SET status = 'approved'
                WHERE user_id = $1 AND time_slot_id = $2 AND status = 'pending'
            ''', user_id, data['time_slot_id'])
            await conn.execute('''
                INSERT INTO meeting_members (meeting_id, user_id) VALUES ($1, $2)
            ''', meeting_id, user_id)
    await callback.message.answer(f"Встреча '{meeting_name}' успешно создана и участники добавлены!")
    await state.clear()

@router.callback_query(F.data.startswith("view_member_"))
async def view_member_profile(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    meeting_id = int(parts[2])
    user_id = int(parts[3])
    # Показываем профиль участника (используем show_applicant_profile)
    await show_applicant_profile(callback, meeting_id, user_id, None, f"members_meeting_{meeting_id}", state)

@router.callback_query(F.data.startswith("add_applicant_to_meeting_"))
async def add_applicant_to_meeting(callback: CallbackQuery, state: FSMContext):
    # Получаем meeting_id из callback_data
    meeting_id = int(callback.data.split("_")[-1])
    # Сохраняем meeting_id в FSM (на всякий случай)
    await state.update_data(meeting_id=meeting_id)
    # Показываем список аппликантов для добавления (используем add_members_to_meeting)
    await add_members_to_meeting(callback.message, state)

@router.callback_query(F.data.startswith("view_applicant_"))
async def view_applicant_profile(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    meeting_id = int(parts[2])
    user_id = int(parts[3])
    status = parts[4] if len(parts) > 4 else None
    await show_applicant_profile(callback, meeting_id, user_id, status, f"add_applicant_to_meeting_{meeting_id}", state)

@router.callback_query(F.data.startswith("approve_and_add_"))
async def approve_and_add_applicant(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    meeting_id = int(parts[3])
    user_id = int(parts[4])
    async with pool.acquire() as conn:
        # Одобряем заявку
        await conn.execute('''
            UPDATE applications SET status = 'approved'
            WHERE user_id = $1 AND status = 'pending'
        ''', user_id)
        # Добавляем в участники встречи
        await conn.execute('''
            INSERT INTO meeting_members (meeting_id, user_id) VALUES ($1, $2)
            ON CONFLICT DO NOTHING
        ''', meeting_id, user_id)
    await callback.answer("Пользователь добавлен во встречу!")
    await show_applicant_profile(callback, meeting_id, user_id, 'approved', f"add_applicant_to_meeting_{meeting_id}", state)

@router.callback_query(F.data.startswith("confirm_add_"))
async def confirm_add_applicant(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    meeting_id = int(parts[2])
    user_id = int(parts[3])
    async with pool.acquire() as conn:
        # Получаем time_slot_id для встречи
        slot_row = await conn.fetchrow('''
            SELECT ts.id
            FROM meeting_time_slots mts
            JOIN time_slots ts ON mts.time_slot_id = ts.id
            WHERE mts.meeting_id = $1
        ''', meeting_id)
        if slot_row:
            time_slot_id = slot_row['id']
            # Откатываем заявку пользователя в статус 'pending'
            await conn.execute('''
                UPDATE applications SET status = 'pending'
                WHERE user_id = $1 AND time_slot_id = $2
            ''', user_id, time_slot_id)
        # Добавляем пользователя обратно во встречу
        await conn.execute('''
            INSERT INTO meeting_members (meeting_id, user_id) VALUES ($1, $2)
            ON CONFLICT DO NOTHING
        ''', meeting_id, user_id)
    await callback.answer("Пользователь возвращён во встречу!")
    await show_applicant_profile(callback, meeting_id, user_id, 'approved', f"members_meeting_{meeting_id}", state)

@router.callback_query(F.data.startswith("remove_member_"))
async def remove_member_from_meeting(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    meeting_id = int(parts[2])
    user_id = int(parts[3])
    async with pool.acquire() as conn:
        await conn.execute('DELETE FROM meeting_members WHERE meeting_id = $1 AND user_id = $2', meeting_id, user_id)
        # Откатываем заявку пользователя на этот timeslot в статус 'pending'
        # Получаем time_slot_id для встречи
        slot_row = await conn.fetchrow('''
            SELECT ts.id
            FROM meeting_time_slots mts
            JOIN time_slots ts ON mts.time_slot_id = ts.id
            WHERE mts.meeting_id = $1
        ''', meeting_id)
        if slot_row:
            time_slot_id = slot_row['id']
            await conn.execute('''
                UPDATE applications SET status = 'pending'
                WHERE user_id = $1 AND time_slot_id = $2
            ''', user_id, time_slot_id)
    await callback.answer("Пользователь удалён из встречи!")
    # После удаления показываем профиль с кнопкой "Вернуть пользователя"
    await show_applicant_profile(callback, meeting_id, user_id, None, f"members_meeting_{meeting_id}", state, show_return_button=True)

@router.callback_query(F.data.startswith("move_member_"))
async def move_member_select_meeting(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    from_meeting_id = int(parts[2])
    user_id = int(parts[3])
    # Получаем город, дату, время текущей встречи
    meeting = await get_meeting(from_meeting_id)
    city_id = meeting['city_id']
    meeting_date = meeting['meeting_date']
    meeting_time = meeting['meeting_time']
    async with pool.acquire() as conn:
        # Ищем другие встречи этого города с тем же временем и датой, кроме текущей, и куда пользователь ещё не добавлен
        meetings = await conn.fetch('''
            SELECT m.id, m.name, m.meeting_date, m.meeting_time, m.venue
            FROM meetings m
            WHERE m.city_id = $1
              AND m.meeting_date = $2
              AND m.meeting_time = $3
              AND m.id != $4
              AND NOT EXISTS (
                  SELECT 1 FROM meeting_members mm WHERE mm.meeting_id = m.id AND mm.user_id = $5
              )
        ''', city_id, meeting_date, meeting_time, from_meeting_id, user_id)
    if not meetings:
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(
            text="Назад",
            callback_data=f"view_member_{from_meeting_id}_{user_id}"
        ))
        builder.add(InlineKeyboardButton(
            text="Главное меню",
            callback_data="meetings_menu"
        ))
        await callback.message.edit_text(
            "Нет подходящих встреч для перемещения этого пользователя.",
            reply_markup=builder.as_markup()
        )
        return
    builder = InlineKeyboardBuilder()
    for m in meetings:
        member_count = await count_meeting_members(m['id'])
        if member_count <= MAX_MEETING_SIZE:
            dots = '🔴' * member_count + '🟢' * (MAX_MEETING_SIZE - member_count)
        else:
            dots = '🔴' * MAX_MEETING_SIZE + f'+{member_count - MAX_MEETING_SIZE}'
        builder.add(InlineKeyboardButton(
            text=f"{dots} {m['meeting_time'].strftime('%H:%M')} {m['meeting_date'].strftime('%d.%m.%Y')}",
            callback_data=f"confirm_move_member_{from_meeting_id}_{m['id']}_{user_id}"
        ))
    builder.add(InlineKeyboardButton(
        text="Назад",
        callback_data=f"view_member_{from_meeting_id}_{user_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="Главное меню",
        callback_data="meetings_menu"
    ))
    builder.adjust(1)
    await callback.message.edit_text(
        "Выберите встречу для перемещения пользователя:",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data.startswith("confirm_move_member_"))
async def confirm_move_member(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    from_meeting_id = int(parts[3])
    to_meeting_id = int(parts[4])
    user_id = int(parts[5])
    # Получаем time_slot_id для обеих встреч
    async with pool.acquire() as conn:
        # time_slot_id from
        slot_row_from = await conn.fetchrow('''
            SELECT ts.id
            FROM meeting_time_slots mts
            JOIN time_slots ts ON mts.time_slot_id = ts.id
            WHERE mts.meeting_id = $1
        ''', from_meeting_id)
        time_slot_id_from = slot_row_from['id'] if slot_row_from else None
        # time_slot_id to
        slot_row_to = await conn.fetchrow('''
            SELECT ts.id
            FROM meeting_time_slots mts
            JOIN time_slots ts ON mts.time_slot_id = ts.id
            WHERE mts.meeting_id = $1
        ''', to_meeting_id)
        time_slot_id_to = slot_row_to['id'] if slot_row_to else None
        # Удаляем из from_meeting, откатываем заявку
        await conn.execute('DELETE FROM meeting_members WHERE meeting_id = $1 AND user_id = $2', from_meeting_id, user_id)
        if time_slot_id_from:
            await conn.execute('''
                UPDATE applications SET status = 'pending'
                WHERE user_id = $1 AND time_slot_id = $2
            ''', user_id, time_slot_id_from)
        # Добавляем в to_meeting, заявку делаем approved
        if time_slot_id_to:
            await conn.execute('''
                UPDATE applications SET status = 'approved'
                WHERE user_id = $1 AND time_slot_id = $2
            ''', user_id, time_slot_id_to)
        await conn.execute('''
            INSERT INTO meeting_members (meeting_id, user_id) VALUES ($1, $2)
            ON CONFLICT DO NOTHING
        ''', to_meeting_id, user_id)
    await callback.answer("Пользователь перемещён во встречу!")
    # Показываем профиль уже в новой встрече
    await show_applicant_profile(callback, to_meeting_id, user_id, 'approved', f"members_meeting_{to_meeting_id}", state)

# --- Обработчик для кнопки 'Изменить время' ---
@router.callback_query(F.data.startswith("edit_meeting_time_"))
async def edit_meeting_time_start(callback: CallbackQuery, state: FSMContext):
    logger.warning(f"[DEBUG] edit_meeting_time_start: callback.data={callback.data}")
    meeting_id = int(callback.data.split('_')[-1])
    await state.update_data(meeting_id=meeting_id)
    await callback.message.edit_text(
        "Пожалуйста, введите новое время для встречи в формате HH:MM (например, 19:30):"
    )
    await state.set_state(MeetingManagementStates.edit_meeting_time)

# --- Обработчик ручного ввода времени ---
@router.message(MeetingManagementStates.edit_meeting_time)
async def edit_meeting_time_manual(message: Message, state: FSMContext):
    from utils.helpers import parse_time
    time_str = message.text.strip()
    meeting_time = parse_time(time_str)
    if not meeting_time:
        await message.answer("Некорректный формат времени. Введите время в формате HH:MM (например, 19:30):")
        return
    data = await state.get_data()
    meeting_id = data.get('meeting_id')
    if not meeting_id:
        await message.answer("Ошибка: не удалось определить встречу.")
        return
    # Обновляем только поле meeting_time
    async with pool.acquire() as conn:
        await conn.execute('''
            UPDATE meetings SET meeting_time = $1 WHERE id = $2
        ''', meeting_time, meeting_id)
    await message.answer("Время встречи успешно обновлено!")
    await state.clear()

@router.callback_query(F.data.startswith("del_"))
async def confirm_delete_meeting(callback: CallbackQuery, state: FSMContext):
    meeting_id = int(callback.data.split("_")[-1])
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="Да, удалить",
        callback_data=f"confirm_del_{meeting_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="Нет, отмена",
        callback_data=f"manage_meeting_{meeting_id}"
    ))
    builder.adjust(2)
    await callback.message.edit_text(
        "⚠️ Вы точно хотите удалить встречу? Это действие нельзя отменить!",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data.startswith("confirm_del_"))
async def delete_meeting_confirmed(callback: CallbackQuery, state: FSMContext):
    meeting_id = int(callback.data.split("_")[-1])
    async with pool.acquire() as conn:
        slot_row = await conn.fetchrow('''
            SELECT ts.id
            FROM meeting_time_slots mts
            JOIN time_slots ts ON mts.time_slot_id = ts.id
            WHERE mts.meeting_id = $1
        ''', meeting_id)
        if slot_row:
            time_slot_id = slot_row['id']
            await conn.execute('''
                UPDATE applications SET status = 'pending'
                WHERE time_slot_id = $1 AND status != 'pending'
            ''', time_slot_id)
        await conn.execute('DELETE FROM meetings WHERE id = $1', meeting_id)
    await callback.message.edit_text("Встреча успешно удалена! Все связанные заявки возвращены в статус 'необработанные'.")
    await state.clear()

@router.callback_query(F.data.startswith("members_meeting_"))
async def show_meeting_members(callback: CallbackQuery, state: FSMContext):
    meeting_id = int(callback.data.split("_")[-1])
    data = await state.get_data()
    city_id = data.get('city_id')
    # Получаем участников встречи
    async with pool.acquire() as conn:
        members = await conn.fetch('''
            SELECT u.id, u.name, u.surname, u.username, u.age
            FROM meeting_members mm
            JOIN users u ON mm.user_id = u.id
            WHERE mm.meeting_id = $1
            ORDER BY mm.added_at
        ''', meeting_id)
    text = f"<b>Участники встречи</b> (всего {len(members)}):\n"
    builder = InlineKeyboardBuilder()
    for i, member in enumerate(members, 1):
        text += f"{i}. {member['name']} {member['surname']} (@{member['username'] or '-'}), {member['age']} лет\n"
        builder.add(InlineKeyboardButton(
            text=f"{member['name']} {member['surname']}",
            callback_data=f"view_member_{meeting_id}_{member['id']}"
        ))
    builder.add(InlineKeyboardButton(
        text="Назад к встрече",
        callback_data=f"manage_meeting_{meeting_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="Назад к списку встреч",
        callback_data=f"list_meetings_city_{city_id}"
    ))
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")

# --- Новый универсальный вызов профиля ---
async def show_applicant_profile(callback, meeting_id, user_id, status, back_callback, state, show_return_button=False):
    if not meeting_id:
        await show_applicant_profile_for_smart(callback, user_id, back_callback, state)
    else:
        await show_applicant_profile_for_meeting(callback, meeting_id, user_id, status, back_callback, state, show_return_button)

# --- Профиль для обычной встречи ---
async def show_applicant_profile_for_meeting(callback, meeting_id, user_id, status, back_callback, state, show_return_button=False):
    async with pool.acquire() as conn:
        user = await conn.fetchrow('SELECT * FROM users WHERE id = $1', user_id)
        meeting = await conn.fetchrow('SELECT * FROM meetings WHERE id = $1', meeting_id)
    if not user or not meeting:
        await callback.message.edit_text("Пользователь или встреча не найдены.")
        return
    text = (
        f"<b>Профиль участника</b>\n"
        f"Имя: {user['name']} {user['surname']}\n"
        f"Возраст: {user['age']}\n"
        f"Username: @{user['username'] or '-'}\n"
        f"Встреча: {meeting['name']}\n"
    )
    builder = InlineKeyboardBuilder()
    if show_return_button:
        builder.add(InlineKeyboardButton(
            text="Вернуть пользователя",
            callback_data=f"confirm_add_{meeting_id}_{user_id}"
        ))
    else:
        builder.add(InlineKeyboardButton(
            text="Удалить из встречи",
            callback_data=f"remove_member_{meeting_id}_{user_id}"
        ))
        builder.add(InlineKeyboardButton(
            text="Переместить в другую встречу",
            callback_data=f"move_member_{meeting_id}_{user_id}"
        ))
    builder.add(InlineKeyboardButton(
        text="Назад к участникам",
        callback_data=f"members_meeting_{meeting_id}"
    ))
    if back_callback:
        builder.add(InlineKeyboardButton(
            text="Назад",
            callback_data=back_callback
        ))
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")

# --- Профиль для smart meeting creation ---
async def show_applicant_profile_for_smart(callback, user_id, back_callback, state):
    async with pool.acquire() as conn:
        user = await conn.fetchrow('SELECT * FROM users WHERE id = $1', user_id)
        answers = await conn.fetch('''
            SELECT q.text, a.answer
            FROM user_answers a
            JOIN questions q ON a.question_id = q.id
            WHERE a.user_id = $1
            ORDER BY q.id
        ''', user_id)
    if not user:
        await callback.message.edit_text("Пользователь не найден.")
        return
    data = await state.get_data()
    smart_selected = data.get('smart_selected_users', []) if data else []
    text = (
        f"<b>Профиль участника</b>\n"
        f"Имя: {user['name']} {user['surname']}\n"
        f"Возраст: {user['age']}\n"
        f"Username: @{user['username'] or '-'}\n"
    )
    builder = InlineKeyboardBuilder()
    if user['status'] == 'rejected':
        text += "\n❌ Пользователь отклонён и не может пользоваться ботом."
        builder.add(InlineKeyboardButton(
            text="Вернуть пользователя",
            callback_data=f"smart_restore_user_{user_id}"
        ))
        builder.add(InlineKeyboardButton(
            text="Назад к списку",
            callback_data="smart_back_to_list"
        ))
    elif user['status'] != 'approved':
        text += "\n<b>Ответы на вопросы:</b>\n"
        for ans in answers:
            text += f"<b>{ans['text']}</b>\n{ans['answer']}\n\n"
        builder.add(InlineKeyboardButton(
            text="Одобрить",
            callback_data=f"smart_approve_user_{user_id}"
        ))
        builder.add(InlineKeyboardButton(
            text="Отклонить (бан)",
            callback_data=f"smart_reject_confirm_{user_id}"
        ))
        builder.add(InlineKeyboardButton(
            text="Назад к списку",
            callback_data="smart_back_to_list"
        ))
    else:
        if user_id in smart_selected:
            text += "\n✅ В списке на добавление"
            builder.add(InlineKeyboardButton(
                text="Удалить из списка",
                callback_data=f"smart_remove_user_{user_id}"
            ))
        else:
            builder.add(InlineKeyboardButton(
                text="Добавить в список",
                callback_data=f"smart_add_user_{user_id}"
            ))
        builder.add(InlineKeyboardButton(
            text="Назад к списку",
            callback_data="smart_back_to_list"
        ))
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")