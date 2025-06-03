from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import time, datetime

from database.db import (
    is_admin, add_timeslot, get_active_timeslots, get_timeslot,
    update_timeslot, delete_timeslot, assign_timeslot_to_meeting,
    remove_timeslot_from_meeting, get_meeting_timeslots, get_meetings_by_timeslot,
    get_meetings_by_status, pool, get_active_cities, get_city, add_user
)
from services.timeslot_service import timeslot_service
from admin_bot.states import TimeslotManagementStates

# Create router
router = Router()

# Timeslots command handler
@router.message(Command("timeslots"))
async def cmd_timeslots(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Check if user is an admin
    if not await is_admin(user_id):
        await message.answer(
            "Sorry, you are not authorized to use this command."
        )
        return
    
    # Create timeslot management keyboard
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Add Time Slot")],
            [KeyboardButton(text="List Time Slots")],
            [KeyboardButton(text="Activate/Deactivate Slot"), KeyboardButton(text="Back to Menu")]
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        "Time Slot Management\n\n"
        "Here you can manage the time slots available for users to select in their applications.",
        reply_markup=keyboard
    )

# Add time slot handler
@router.message(F.text == "Add Time Slot")
async def add_timeslot_command(message: Message, state: FSMContext):
    # Check if user is an admin
    if not await is_admin(message.from_user.id):
        return
    # Получаем список городов
    cities = await get_active_cities()
    if not cities:
        await message.answer("Нет активных городов. Сначала создайте город.")
        return
    builder = InlineKeyboardBuilder()
    for city in cities:
        builder.add(InlineKeyboardButton(
            text=city['name'],
            callback_data=f"select_city_{city['id']}"
        ))
    builder.adjust(2)
    await message.answer(
        "Выберите город для нового таймслота:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(TimeslotManagementStates.add_city)

# Обработчик выбора города
@router.callback_query(TimeslotManagementStates.add_city, F.data.startswith("select_city_"))
async def process_add_city(callback: CallbackQuery, state: FSMContext):
    city_id = int(callback.data.split('_')[-1])
    await state.update_data(city_id=city_id)
    # Дальше стандартный flow: выбор дня недели
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Monday"), KeyboardButton(text="Tuesday")],
            [KeyboardButton(text="Wednesday"), KeyboardButton(text="Thursday")],
            [KeyboardButton(text="Friday"), KeyboardButton(text="Saturday")],
            [KeyboardButton(text="Sunday"), KeyboardButton(text="Cancel")]
        ],
        resize_keyboard=True
    )
    await callback.message.answer(
        "Пожалуйста, выберите день недели для нового таймслота:",
        reply_markup=keyboard
    )
    await state.set_state(TimeslotManagementStates.add_day)
    await callback.answer()

# Process day selection
@router.message(TimeslotManagementStates.add_day)
async def process_add_day(message: Message, state: FSMContext):
    day = message.text.strip()
    
    # Check if cancelled
    if day.lower() == "cancel":
        await cancel_timeslot_operation(message, state)
        return
    
    # Validate day
    valid_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    if day not in valid_days:
        await message.answer(
            "Please select a valid day of the week from the keyboard."
        )
        return
    
    # Save day to state
    await state.update_data(day=day)
    
    await message.answer(
        "Please enter the start time for this slot in 24-hour format (HH:MM):"
    )
    
    # Set state to wait for start time
    await state.set_state(TimeslotManagementStates.add_start_time)

# Process start time input
@router.message(TimeslotManagementStates.add_start_time)
async def process_add_start_time(message: Message, state: FSMContext):
    time_str = message.text.strip()
    
    # Parse and validate time format using helper function
    from utils.helpers import parse_time
    
    start_time = parse_time(time_str)
    
    if not start_time:
        await message.answer(
            "Invalid time format. Please enter the time in 24-hour format (HH:MM or HH.MM):"
        )
        return
    
    # Save start time to state
    await state.update_data(start_time=start_time)
    
    await message.answer(
        "Please enter the end time for this slot in 24-hour format (HH:MM):"
        "\nLeave empty to set end time as start time + 1 hour."
    )
    
    # Set state to wait for end time
    await state.set_state(TimeslotManagementStates.add_end_time)

# Process end time input
@router.message(TimeslotManagementStates.add_end_time)
async def process_add_end_time(message: Message, state: FSMContext):
    time_str = message.text.strip()
    data = await state.get_data()
    day = data['day']
    start_time = data['start_time']
    city_id = data['city_id']
    end_time = None
    if not time_str:
        start_hour = start_time.hour
        end_hour = (start_hour + 1) % 24
        end_time = time(end_hour, start_time.minute)
    else:
        from utils.helpers import parse_time
        end_time = parse_time(time_str)
        if not end_time:
            await message.answer(
                "Invalid time format. Please enter the time in 24-hour format (HH:MM or HH.MM):"
                "\nOr leave empty to set end time as start time + 1 hour."
            )
            return
    if end_time <= start_time:
        if end_time.hour < start_time.hour:
            pass
        else:
            await message.answer(
                "End time must be after start time. Please enter a valid end time:"
            )
            return
    await state.update_data(end_time=end_time)
    try:
        await add_timeslot(day, start_time, end_time, city_id)
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Add Time Slot")],
                [KeyboardButton(text="List Time Slots")],
                [KeyboardButton(text="Activate/Deactivate Slot"), KeyboardButton(text="Back to Menu")]
            ],
            resize_keyboard=True
        )
        await message.answer(
            f"Time slot '{day} {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}' успешно добавлен!",
            reply_markup=keyboard
        )
    except Exception as e:
        await message.answer(
            f"Не удалось добавить таймслот: {str(e)}\nВозможно, такой таймслот уже существует."
        )
    await state.clear()

# List time slots handler
@router.message(F.text == "List Time Slots")
async def list_timeslots(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    timeslots = await get_active_timeslots()
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Add Time Slot")],
            [KeyboardButton(text="List Time Slots")],
            [KeyboardButton(text="Activate/Deactivate Slot"), KeyboardButton(text="Back to Menu")]
        ],
        resize_keyboard=True
    )
    if not timeslots:
        await message.answer("Нет активных таймслотов.", reply_markup=keyboard)
        await state.clear()
        return
    text = "Список таймслотов по городам:\n\n"
    city_cache = {}
    for ts in timeslots:
        city_id = ts['city_id']
        if city_id not in city_cache:
            city = await get_city(city_id)
            city_cache[city_id] = city['name'] if city else f"id={city_id}"
        text += f"{city_cache[city_id]}: {ts['day_of_week']} {ts['start_time'].strftime('%H:%M')} - {ts['end_time'].strftime('%H:%M')}\n"
    await message.answer(text, reply_markup=keyboard)
    await state.clear()
    
    # Set state to wait for time slot selection
    await state.set_state(TimeslotManagementStates.select_timeslot_to_edit)

# Handle time slot selection for editing
@router.callback_query(TimeslotManagementStates.select_timeslot_to_edit, F.data.startswith("edit_timeslot_"))
async def handle_edit_timeslot_selection(callback: CallbackQuery, state: FSMContext):
    # Extract time slot ID from callback data
    time_slot_id = int(callback.data.split('_')[-1])
    
    # Get time slot information
    timeslot = await get_timeslot(time_slot_id)
    
    if not timeslot:
        await callback.message.answer("Time slot not found. Please try again.")
        await callback.answer()
        return
    
    # Save time slot info to state
    await state.update_data(
        time_slot_id=time_slot_id,
        day=timeslot['day_of_week'],
        start_time=timeslot['start_time'],
        end_time=timeslot['end_time']
    )
    
    # Create edit options keyboard
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="Edit Day", callback_data="edit_day"),
        InlineKeyboardButton(text="Edit Start Time", callback_data="edit_start_time"),
        InlineKeyboardButton(text="Edit End Time", callback_data="edit_end_time"),
        InlineKeyboardButton(text="Delete Time Slot", callback_data="delete_timeslot"),
        InlineKeyboardButton(text="Cancel", callback_data="cancel_edit")
    )
    builder.adjust(2)
    
    active_status = "Active" if timeslot['active'] else "Inactive"
    
    await callback.message.edit_text(
        f"Time Slot Details:\n\n"
        f"Day: {timeslot['day_of_week']}\n"
        f"Start Time: {timeslot['start_time'].strftime('%H:%M')}\n"
        f"End Time: {timeslot['end_time'].strftime('%H:%M')}\n"
        f"Status: {active_status}\n\n"
        f"What would you like to do with this time slot?",
        reply_markup=builder.as_markup()
    )
    
    await callback.answer()

# Cancel operation handler
async def cancel_timeslot_operation(message: Message, state: FSMContext):
    # Create timeslot management keyboard
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Add Time Slot")],
            [KeyboardButton(text="List Time Slots")],
            [KeyboardButton(text="Activate/Deactivate Slot"), KeyboardButton(text="Back to Menu")]
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        "Operation cancelled.",
        reply_markup=keyboard
    )
    
    # Clear state
    await state.clear()

# Back to menu handler
@router.message(F.text == "Back to Menu")
async def back_to_menu(message: Message, state: FSMContext):
    # Check if user is an admin
    if not await is_admin(message.from_user.id):
        return
    
    # Create admin keyboard
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="/cities"), KeyboardButton(text="/timeslots")],
            [KeyboardButton(text="/questions"), KeyboardButton(text="/applications")],
            [KeyboardButton(text="/meetings")]
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        "Main Menu",
        reply_markup=keyboard
    )
    
    # Clear state
    await state.clear()

# Handle edit day selection
@router.callback_query(TimeslotManagementStates.select_timeslot_to_edit, F.data == "edit_day")
async def handle_edit_day(callback: CallbackQuery, state: FSMContext):
    # Create day selection keyboard
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Monday"), KeyboardButton(text="Tuesday")],
            [KeyboardButton(text="Wednesday"), KeyboardButton(text="Thursday")],
            [KeyboardButton(text="Friday"), KeyboardButton(text="Saturday")],
            [KeyboardButton(text="Sunday"), KeyboardButton(text="Cancel")]
        ],
        resize_keyboard=True
    )
    
    await callback.message.answer(
        "Please select the new day of the week:",
        reply_markup=keyboard
    )
    
    # Set state to wait for day selection
    await state.set_state(TimeslotManagementStates.edit_day)
    await callback.answer()

# Process day edit
@router.message(TimeslotManagementStates.edit_day)
async def process_edit_day(message: Message, state: FSMContext):
    new_day = message.text.strip()
    
    # Check if cancelled
    if new_day.lower() == "cancel":
        await cancel_timeslot_operation(message, state)
        return
    
    # Validate day
    valid_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    if new_day not in valid_days:
        await message.answer(
            "Please select a valid day of the week from the keyboard."
        )
        return
    
    # Get data from state
    data = await state.get_data()
    time_slot_id = data['time_slot_id']
    
    # Update time slot in database
    try:
        success = await update_timeslot(time_slot_id, day_of_week=new_day)
        
        if success:
            await message.answer(f"Time slot day updated to {new_day} successfully!")
        else:
            await message.answer("Failed to update time slot. Please try again.")
    except Exception as e:
        await message.answer(f"Error updating time slot: {str(e)}")
    
    # Clear state and return to time slot management
    await return_to_timeslot_management(message, state)

# Handle edit start time request
@router.callback_query(TimeslotManagementStates.select_timeslot_to_edit, F.data == "edit_start_time")
async def handle_edit_start_time(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "Please enter the new start time for this slot in 24-hour format (HH:MM):"
    )
    await state.set_state(TimeslotManagementStates.edit_start_time)
    await callback.answer()

# Process edited start time
@router.message(TimeslotManagementStates.edit_start_time)
async def process_edit_start_time(message: Message, state: FSMContext):
    time_str = message.text.strip()
    
    # Parse and validate time format using helper function
    from utils.helpers import parse_time
    
    start_time = parse_time(time_str)
    
    if not start_time:
        await message.answer(
            "Invalid time format. Please enter the time in 24-hour format (HH:MM or HH.MM):"
        )
        return
    
    # Get time slot info from state
    data = await state.get_data()
    time_slot_id = data['time_slot_id']
    day = data['day']
    end_time = data['end_time']
    
    # Check if start time is before end time
    if start_time >= end_time and start_time.hour >= end_time.hour:
        await message.answer(
            "Start time must be before end time. Please enter a valid start time:"
        )
        return
    
    # Update time slot in database
    try:
        success = await update_timeslot(time_slot_id, start_time=start_time)
        if success:
            await message.answer(
                f"Time slot updated successfully: {day} {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}"
            )
            await return_to_timeslot_management(message, state)
        else:
            await message.answer(
                "Failed to update time slot. Please try again."
            )
    except Exception as e:
        await message.answer(
            f"Error updating time slot: {str(e)}"
        )

# Handle edit end time request
@router.callback_query(TimeslotManagementStates.select_timeslot_to_edit, F.data == "edit_end_time")
async def handle_edit_end_time(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "Please enter the new end time for this slot in 24-hour format (HH:MM):"
    )
    await state.set_state(TimeslotManagementStates.edit_end_time)
    await callback.answer()

# Process edited end time
@router.message(TimeslotManagementStates.edit_end_time)
async def process_edit_end_time(message: Message, state: FSMContext):
    time_str = message.text.strip()
    
    # Parse and validate time format using helper function
    from utils.helpers import parse_time
    
    end_time = parse_time(time_str)
    
    if not end_time:
        await message.answer(
            "Invalid time format. Please enter the time in 24-hour format (HH:MM or HH.MM):"
        )
        return
    
    # Get time slot info from state
    data = await state.get_data()
    time_slot_id = data['time_slot_id']
    day = data['day']
    start_time = data['start_time']
    
    # Check if end time is after start time
    if end_time <= start_time:
        # Handle case when end time is on the next day
        if end_time.hour < start_time.hour:
            # This is fine, it crosses midnight
            pass
        else:
            await message.answer(
                "End time must be after start time. Please enter a valid end time:"
            )
            return
    
    # Update time slot in database
    try:
        success = await update_timeslot(time_slot_id, end_time=end_time)
        if success:
            await message.answer(
                f"Time slot updated successfully: {day} {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}"
            )
            await return_to_timeslot_management(message, state)
        else:
            await message.answer(
                "Failed to update time slot. Please try again."
            )
    except Exception as e:
        await message.answer(
            f"Error updating time slot: {str(e)}"
        )

# Handle delete time slot selection
@router.callback_query(TimeslotManagementStates.select_timeslot_to_edit, F.data == "delete_timeslot")
async def handle_delete_timeslot(callback: CallbackQuery, state: FSMContext):
    # Create confirmation keyboard
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="Yes, delete", callback_data="confirm_delete"),
        InlineKeyboardButton(text="No, cancel", callback_data="cancel_delete")
    )
    
    await callback.message.answer(
        "Are you sure you want to delete this time slot? This action cannot be undone.",
        reply_markup=builder.as_markup()
    )
    
    # Set state to wait for confirmation
    await state.set_state(TimeslotManagementStates.confirm_delete)
    await callback.answer()

# Handle delete confirmation
@router.callback_query(TimeslotManagementStates.confirm_delete, F.data == "confirm_delete")
async def handle_confirm_delete(callback: CallbackQuery, state: FSMContext):
    # Get time slot ID from state
    data = await state.get_data()
    time_slot_id = data['time_slot_id']
    
    # Delete time slot from database (set to inactive)
    try:
        success = await delete_timeslot(time_slot_id)
        
        if success:
            await callback.message.answer("Time slot has been deactivated successfully!")
        else:
            await callback.message.answer("Failed to deactivate time slot. Please try again.")
    except Exception as e:
        await callback.message.answer(f"Error deactivating time slot: {str(e)}")
    
    # Clear state and return to time slot management
    await return_to_timeslot_management_callback(callback, state)

# Handle cancel delete
@router.callback_query(TimeslotManagementStates.confirm_delete, F.data == "cancel_delete")
async def handle_cancel_delete(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Time slot deletion cancelled.")
    
    # Clear state and return to time slot management
    await return_to_timeslot_management_callback(callback, state)

# Handle cancel edit
@router.callback_query(TimeslotManagementStates.select_timeslot_to_edit, F.data == "cancel_edit")
async def handle_cancel_edit(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Time slot editing cancelled.")
    
    # Clear state and return to time slot management
    await return_to_timeslot_management_callback(callback, state)

# Return to time slot management helper for message-based handlers
async def return_to_timeslot_management(message: Message, state: FSMContext):
    # Create timeslot management keyboard
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Add Time Slot")],
            [KeyboardButton(text="List Time Slots")],
            [KeyboardButton(text="Activate/Deactivate Slot"), KeyboardButton(text="Back to Menu")]
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        "Returning to Time Slot Management.",
        reply_markup=keyboard
    )
    
    # Clear state
    await state.clear()

# Return to time slot management helper for callback-based handlers
async def return_to_timeslot_management_callback(callback: CallbackQuery, state: FSMContext):
    # Create timeslot management keyboard
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Add Time Slot")],
            [KeyboardButton(text="List Time Slots")],
            [KeyboardButton(text="Activate/Deactivate Slot"), KeyboardButton(text="Back to Menu")]
        ],
        resize_keyboard=True
    )
    
    await callback.message.answer(
        "Returning to Time Slot Management.",
        reply_markup=keyboard
    )
    
    # Clear state
    await state.clear()

# --- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ ОТОБРАЖЕНИЯ СПИСКА ТАЙМСЛОТОВ ---
def get_timeslot_list_text_and_keyboard(timeslots):
    text = "Toggle Time Slot Status:\n\n✅ = Active, ❌ = Inactive\n\nClick on a time slot to toggle its status:"
    builder = InlineKeyboardBuilder()
    for slot in timeslots:
        active_status = "✅" if slot['active'] else "❌"
        builder.add(InlineKeyboardButton(
            text=f"{active_status} {slot['day_of_week']} {slot['start_time'].strftime('%H:%M')} - {slot['end_time'].strftime('%H:%M')}",
            callback_data=f"toggle_slot_{slot['id']}"
        ))
    builder.add(InlineKeyboardButton(text="Back", callback_data="back_to_timeslot_management"))
    return text, builder.as_markup()

# --- ОБНОВЛЁННЫЙ ОБРАБОТЧИК АКТИВАЦИИ/ДЕАКТИВАЦИИ ---
@router.message(F.text == "Activate/Deactivate Slot")
async def activate_deactivate_timeslot(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    cities = await get_active_cities()
    if not cities:
        await message.answer("Нет активных городов. Сначала создайте город.")
        return
    builder = InlineKeyboardBuilder()
    for city in cities:
        builder.add(InlineKeyboardButton(text=city['name'], callback_data=f"select_city_for_timeslots_{city['id']}"))
    await message.answer("Выберите город для управления таймслотами:", reply_markup=builder.as_markup())
    await state.set_state(TimeslotManagementStates.select_city_for_toggle)

@router.callback_query(F.data.startswith("select_city_for_timeslots_"), TimeslotManagementStates.select_city_for_toggle)
async def select_city_for_toggle(callback: CallbackQuery, state: FSMContext):
    city_id = int(callback.data.split("_")[-1])
    await state.update_data(city_id=city_id)
    # Получаем таймслоты только для выбранного города
    async with pool.acquire() as conn:
        timeslots = await conn.fetch('''
            SELECT * FROM time_slots WHERE city_id = $1
            ORDER BY CASE
                WHEN day_of_week = 'Monday' THEN 1
                WHEN day_of_week = 'Tuesday' THEN 2
                WHEN day_of_week = 'Wednesday' THEN 3
                WHEN day_of_week = 'Thursday' THEN 4
                WHEN day_of_week = 'Friday' THEN 5
                WHEN day_of_week = 'Saturday' THEN 6
                WHEN day_of_week = 'Sunday' THEN 7
            END, start_time
        ''', city_id)
    text, keyboard = get_timeslot_list_text_and_keyboard(timeslots)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(TimeslotManagementStates.activate_deactivate)

@router.callback_query(TimeslotManagementStates.activate_deactivate, F.data.startswith("toggle_slot_"))
async def handle_toggle_slot(callback: CallbackQuery, state: FSMContext):
    time_slot_id = int(callback.data.split('_')[-1])
    data = await state.get_data()
    city_id = data.get('city_id')
    timeslot = await get_timeslot(time_slot_id)
    if not timeslot:
        await callback.answer("Time slot not found.", show_alert=True)
        return
    new_status = not timeslot['active']
    try:
        success = await update_timeslot(time_slot_id, active=new_status)
        if success:
            status_text = "activated" if new_status else "deactivated"
            # Получаем обновлённый список таймслотов только для выбранного города
            async with pool.acquire() as conn:
                timeslots = await conn.fetch('''
                    SELECT * FROM time_slots WHERE city_id = $1
                    ORDER BY CASE
                        WHEN day_of_week = 'Monday' THEN 1
                        WHEN day_of_week = 'Tuesday' THEN 2
                        WHEN day_of_week = 'Wednesday' THEN 3
                        WHEN day_of_week = 'Thursday' THEN 4
                        WHEN day_of_week = 'Friday' THEN 5
                        WHEN day_of_week = 'Saturday' THEN 6
                        WHEN day_of_week = 'Sunday' THEN 7
                    END, start_time
                ''', city_id)
            text, keyboard = get_timeslot_list_text_and_keyboard(timeslots)
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer(f"Time slot has been {status_text} successfully!", show_alert=False)
        else:
            await callback.answer("Failed to update time slot status.", show_alert=True)
    except Exception as e:
        await callback.answer(f"Error updating time slot status: {str(e)}", show_alert=True)

# Function to register handlers with the dispatcher
def register_timeslots_handlers(dp):
    dp.include_router(router)

@router.callback_query(F.data == "back_to_timeslot_management")
async def back_to_timeslot_management(callback: CallbackQuery, state: FSMContext):
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Add Time Slot")],
            [KeyboardButton(text="List Time Slots")],
            [KeyboardButton(text="Activate/Deactivate Slot"), KeyboardButton(text="Back to Menu")]
        ],
        resize_keyboard=True
    )
    await callback.message.answer(
        "Time Slot Management\n\nHere you can manage the time slots available for users to select in their applications.",
        reply_markup=keyboard
    )
    await state.clear()
    await callback.answer()

@router.message(Command("generate_fake_applicants"))
async def generate_fake_applicants(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    # Получаем id первого активного таймслота в Варшаве
    async with pool.acquire() as conn:
        city = await conn.fetchrow("SELECT id FROM cities WHERE name='Warsaw' AND active=TRUE LIMIT 1")
        if not city:
            await message.answer("Нет активного города Варшава!")
            return
        timeslot = await conn.fetchrow("SELECT id FROM time_slots WHERE city_id=$1 AND active=TRUE LIMIT 1", city['id'])
        if not timeslot:
            await message.answer("Нет активных таймслотов в Варшаве!")
            return
        timeslot_id = timeslot['id']
        # Создаём 30 пользователей и 30 заявок
        for i in range(1, 31):
            username = f"fakeuser{i}"
            name = f"Имя{i}"
            surname = f"Фамилия{i}"
            age = 20 + (i % 15)
            await conn.execute(
                """
                INSERT INTO users (username, name, surname, age, registration_date, status)
                VALUES ($1, $2, $3, $4, CURRENT_DATE - $5 * INTERVAL '1 day', 'pending')
                ON CONFLICT (username) DO UPDATE SET name=EXCLUDED.name RETURNING id
                """, username, name, surname, age, i
            )
            user_id_row = await conn.fetchrow("SELECT id FROM users WHERE username=$1", username)
            user_id = user_id_row['id']
            await conn.execute(
                """
                INSERT INTO applications (user_id, created_at, time_slot_id, status)
                VALUES ($1, NOW() - $2 * INTERVAL '1 hour', $3, 'pending')
                ON CONFLICT (user_id, time_slot_id) DO NOTHING
                """, user_id, i, timeslot_id
            )
    await message.answer("30 фейковых аппликантов успешно созданы!")