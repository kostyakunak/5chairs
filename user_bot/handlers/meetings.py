from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardRemove
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta

from database.db import get_user, get_user_meetings, get_meeting_members, get_meeting, pool, remove_meeting_member, get_user_applications
from user_bot.handlers.start import get_main_menu, show_main_menu

# Create router
router = Router()

# Function to register handlers with the dispatcher
def register_meetings_handlers(dp):
    dp.include_router(router)

@router.message(Command("my_meetings"))
async def cmd_meetings(event, state: FSMContext, is_callback: bool = False):
    user_id = event.from_user.id if not is_callback else event.from_user.id
    async with pool.acquire() as conn:
        meetings = await conn.fetch(
            '''
            SELECT m.*, c.name as city_name,
                   CASE 
                       WHEN m.venue ~ '^[0-9]+$' THEN 
                           (SELECT v.name FROM venues v WHERE v.id = m.venue::int)
                       ELSE m.venue 
                   END as venue_display
            FROM meetings m
            JOIN meeting_members mm ON m.id = mm.meeting_id
            JOIN cities c ON m.city_id = c.id
            WHERE mm.user_id = $1 AND m.status = 'planned'
            ORDER BY m.meeting_date, m.meeting_time
            ''',
            user_id
        )
    
    builder = InlineKeyboardBuilder()
    
    if not meetings:
        builder.button(text="В меню", callback_data="main_menu")
        builder.adjust(1)
        text = "📅 У вас нет назначенных встреч.\n\nПодайте заявку, чтобы попасть на следующую встречу!"
        if is_callback:
            msg = await event.message.edit_text(text, reply_markup=builder.as_markup())
            await state.update_data(last_private_message_id=msg.message_id)
        else:
            msg = await event.answer(text, reply_markup=builder.as_markup())
            await state.update_data(last_private_message_id=msg.message_id)
        return

    for m in meetings:
        venue_name = m['venue_display'] if m['venue_display'] and m['venue_display'] != "-" else "место уточняется"
        # Форматируем дату более красиво
        date_str = m['meeting_date'].strftime('%d.%m')
        time_str = m['meeting_time'].strftime('%H:%M')
        btn_text = f"📍 {date_str}, {time_str}, {venue_name}"
        builder.button(text=btn_text, callback_data=f"meeting_details_{m['id']}")
    
    builder.button(text="📅 Прошедшие встречи", callback_data="past_meetings")
    builder.button(text="В меню", callback_data="main_menu")
    builder.adjust(1)
    
    # Отправляем сообщение только с кнопками, без текста
    if is_callback:
        msg = await event.message.edit_text(".", reply_markup=builder.as_markup())
        await state.update_data(last_private_message_id=msg.message_id)
    else:
        msg = await event.answer(".", reply_markup=builder.as_markup())
        await state.update_data(last_private_message_id=msg.message_id)

# Обработчик для показа деталей встречи
@router.callback_query(F.data.startswith("meeting_details_"))
async def show_meeting_details(callback: CallbackQuery, state: FSMContext):
    meeting_id = int(callback.data.split("_")[2])
    async with pool.acquire() as conn:
        meeting = await conn.fetchrow(
            '''
            SELECT m.*, c.name as city_name,
                   CASE 
                       WHEN m.venue ~ '^[0-9]+$' THEN 
                           (SELECT v.name FROM venues v WHERE v.id = m.venue::int)
                       ELSE NULL 
                   END as venue_name
            FROM meetings m
            JOIN cities c ON m.city_id = c.id
            WHERE m.id = $1
            ''',
            meeting_id
        )
    
    if not meeting:
        msg = await callback.message.edit_text("Встреча не найдена.", reply_markup=None)
        await state.update_data(last_private_message_id=msg.message_id)
        return
    
    text = (
        f"📅 Дата и время: {meeting['meeting_date'].strftime('%d.%m.%Y')} {meeting['meeting_time'].strftime('%H:%M')}\n"
        f"📍 Город: {meeting['city_name']}\n"
    )
    
    # Определяем название места
    if meeting['venue_name']:
        text += f"🧭 Место: {meeting['venue_name']}\n"
    elif meeting['venue'] and meeting['venue'] != "-":
        text += f"🧭 Место: {meeting['venue']}\n"
    else:
        text += f"🧭 Место: уточняется\n"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="В меню", callback_data="main_menu")
    builder.adjust(1)
    
    msg = await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await state.update_data(last_private_message_id=msg.message_id)

# Back to meetings list handler
@router.callback_query(F.data == "back_to_meetings")
async def back_to_meetings(callback, state: FSMContext):
    """Return to meetings list"""
    # Call the meetings command handler with the callback message
    message = callback.message
    message.from_user = callback.from_user
    await cmd_meetings(message, state, is_callback=True)

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
    builder = InlineKeyboardBuilder()
    builder.button(text="Да, выйти", callback_data=f"do_cancel_meeting_{meeting_id}")
    builder.button(text="Нет", callback_data="cancel_cancel_meeting")
    builder.button(text="В меню", callback_data="main_menu")
    builder.adjust(1)
    msg = await callback.message.edit_text(
        f"Вы уверены, что хотите отменить участие во встрече id={meeting_id}?",
        reply_markup=builder.as_markup()
    )
    await state.update_data(last_private_message_id=msg.message_id)

# Обработка подтверждения отмены
@router.callback_query(F.data.startswith("do_cancel_meeting_"))
async def do_cancel_meeting(callback: CallbackQuery, state: FSMContext):
    meeting_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    await remove_meeting_member(meeting_id, user_id)
    builder = InlineKeyboardBuilder()
    builder.button(text="В меню", callback_data="main_menu")
    builder.adjust(1)
    msg = await callback.message.edit_text("Вы вышли из встречи.", reply_markup=builder.as_markup())
    await state.update_data(last_private_message_id=msg.message_id)
    meetings = await get_user_meetings(user_id)
    if not meetings:
        msg2 = await callback.message.answer("У вас больше нет встреч.", reply_markup=builder.as_markup())
        await state.update_data(last_private_message_id=msg2.message_id)
        return
    text = "Ваши встречи:\n"
    builder2 = InlineKeyboardBuilder()
    for m in meetings:
        text += f"\n{m['meeting_date'].strftime('%d.%m.%Y')} {m['meeting_time'].strftime('%H:%M')} — {m['city_name']} (id={m['id']})"
        builder2.add(InlineKeyboardButton(
            text=f"Отменить встречу {m['id']}",
            callback_data=f"cancel_meeting_{m['id']}"
        ))
    builder2.button(text="В меню", callback_data="main_menu")
    builder2.adjust(1)
    msg3 = await callback.message.answer(text, reply_markup=builder2.as_markup())
    await state.update_data(last_private_message_id=msg3.message_id)

# Отмена отмены (оставить встречу)
@router.callback_query(F.data == "cancel_cancel_meeting")
async def cancel_cancel_meeting(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    meetings = await get_user_meetings(user_id)
    if not meetings:
        builder = InlineKeyboardBuilder()
        builder.button(text="В меню", callback_data="main_menu")
        builder.adjust(1)
        msg = await callback.message.edit_text("У вас пока нет встреч.", reply_markup=builder.as_markup())
        await state.update_data(last_private_message_id=msg.message_id)
        return
    text = "Ваши встречи:\n"
    builder = InlineKeyboardBuilder()
    for m in meetings:
        text += f"\n{m['meeting_date'].strftime('%d.%m.%Y')} {m['meeting_time'].strftime('%H:%M')} — {m['city_name']} (id={m['id']})"
        builder.add(InlineKeyboardButton(
            text=f"Отменить встречу {m['id']}",
            callback_data=f"cancel_meeting_{m['id']}"
        ))
    builder.button(text="В меню", callback_data="main_menu")
    builder.adjust(1)
    msg = await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await state.update_data(last_private_message_id=msg.message_id)

@router.callback_query(F.data.startswith("leave_feedback_"))
async def leave_feedback(callback: CallbackQuery, state: FSMContext):
    meeting_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    await state.update_data(feedback_meeting_id=meeting_id)
    builder = InlineKeyboardBuilder()
    builder.button(text="В меню", callback_data="main_menu")
    builder.adjust(1)
    msg = await callback.message.edit_text(
        "Пожалуйста, оцените встречу по 5-балльной шкале (1 — плохо, 5 — отлично):",
        reply_markup=builder.as_markup()
    )
    await state.update_data(last_private_message_id=msg.message_id)

@router.message(lambda message, state: state.get_state() == "feedback_rating")
async def get_feedback_rating(message: Message, state: FSMContext):
    try:
        rating = int(message.text.strip())
        if rating < 1 or rating > 5:
            await message.answer("Пожалуйста, введите число от 1 до 5.")
            return
        await state.update_data(feedback_rating=rating)
        await message.answer("Спасибо! Теперь напишите короткий комментарий о встрече:")
        await state.set_state("feedback_comment")
    except Exception:
        await message.answer("Пожалуйста, введите число от 1 до 5.")

@router.message(lambda message, state: state.get_state() == "feedback_comment")
async def get_feedback_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    meeting_id = data.get("feedback_meeting_id")
    rating = data.get("feedback_rating")
    comment = message.text.strip()
    user_id = message.from_user.id
    # Здесь должен быть вызов функции сохранения отзыва в БД, например:
    # await save_meeting_feedback(meeting_id, user_id, rating, comment)
    builder = InlineKeyboardBuilder()
    builder.button(text="В меню", callback_data="main_menu")
    builder.adjust(1)
    await message.answer("Спасибо за ваш отзыв!", reply_markup=builder.as_markup())
    await state.clear()

# Новый обработчик для кнопки "Прошедшие встречи"
@router.callback_query(F.data == "past_meetings")
async def show_past_meetings(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    # Получаем встречи пользователя со статусом 'completed'
    async with pool.acquire() as conn:
        meetings = await conn.fetch(
            '''
            SELECT m.*, c.name as city_name,
                   CASE 
                       WHEN m.venue ~ '^[0-9]+$' THEN 
                           (SELECT v.name FROM venues v WHERE v.id = m.venue::int)
                       ELSE m.venue 
                   END as venue_display
            FROM meetings m
            JOIN meeting_members mm ON m.id = mm.meeting_id
            JOIN cities c ON m.city_id = c.id
            WHERE mm.user_id = $1 AND m.status = 'completed'
            ORDER BY m.meeting_date DESC, m.meeting_time DESC
            ''',
            user_id
        )
    
    builder = InlineKeyboardBuilder()
    
    if not meetings:
        builder.button(text="🏠 В меню", callback_data="main_menu")
        builder.adjust(1)
        msg = await callback.message.edit_text(
            "📜 У вас пока нет завершённых встреч.\n\nКогда вы посетите встречи, они появятся здесь.",
            reply_markup=builder.as_markup()
        )
        await state.update_data(last_private_message_id=msg.message_id)
        return
    
    for m in meetings:
        venue_name = m['venue_display'] if m['venue_display'] and m['venue_display'] != "-" else "место не указано"
        # Форматируем дату более красиво для прошедших встреч
        date_str = m['meeting_date'].strftime('%d.%m')
        time_str = m['meeting_time'].strftime('%H:%M')
        btn_text = f"📍 {date_str}, {time_str}, {venue_name}"
        builder.button(text=btn_text, callback_data=f"past_meeting_details_{m['id']}")
    
    builder.button(text="В меню", callback_data="main_menu")
    builder.adjust(1)
    
    msg = await callback.message.edit_text(".", reply_markup=builder.as_markup())
    await state.update_data(last_private_message_id=msg.message_id)

# Обработчик для показа деталей прошедших встреч
@router.callback_query(F.data.startswith("past_meeting_details_"))
async def show_past_meeting_details(callback: CallbackQuery, state: FSMContext):
    meeting_id = int(callback.data.split("_")[3])
    async with pool.acquire() as conn:
        # Получаем информацию о встрече
        meeting = await conn.fetchrow(
            '''
            SELECT m.*, c.name as city_name,
                   CASE 
                       WHEN m.venue ~ '^[0-9]+$' THEN 
                           (SELECT v.name FROM venues v WHERE v.id = m.venue::int)
                       ELSE NULL 
                   END as venue_name
            FROM meetings m
            JOIN cities c ON m.city_id = c.id
            WHERE m.id = $1
            ''',
            meeting_id
        )
        
        # Получаем участников встречи
        participants = await conn.fetch(
            '''
            SELECT u.id, u.name, u.surname 
            FROM meeting_members mm
            JOIN users u ON mm.user_id = u.id
            WHERE mm.meeting_id = $1
            ORDER BY u.name, u.surname
            ''',
            meeting_id
        )
    
    if not meeting:
        msg = await callback.message.edit_text("❌ Встреча не найдена.", reply_markup=None)
        await state.update_data(last_private_message_id=msg.message_id)
        return
    
    text = (
        f"📅 Дата и время: {meeting['meeting_date'].strftime('%d.%m.%Y')} {meeting['meeting_time'].strftime('%H:%M')}\n"
        f"📍 Город: {meeting['city_name']}\n"
    )
    
    # Определяем название места
    if meeting['venue_name']:
        text += f"🧭 Место: {meeting['venue_name']}\n"
    elif meeting['venue'] and meeting['venue'] != "-":
        text += f"🧭 Место: {meeting['venue']}\n"
    else:
        text += f"🧭 Место: не указано\n"
    
    builder = InlineKeyboardBuilder()
    
    # Добавляем информацию об участниках
    if participants:
        text += f"\n👥 Участники ({len(participants)}):\n"
        text += "Нажмите на участника для просмотра профиля:\n"
        for p in participants:
            btn_text = f"👤 {p['name']} {p['surname']}"
            builder.button(text=btn_text, callback_data=f"participant_info_{p['id']}_{meeting_id}")
    else:
        text += f"\n👥 Участники: информация недоступна\n"
    
    builder.button(text="В меню", callback_data="main_menu")
    builder.adjust(1)
    
    msg = await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await state.update_data(last_private_message_id=msg.message_id)

# Обработчик для показа информации об участнике встречи
@router.callback_query(F.data.startswith("participant_info_"))
async def show_participant_info(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    user_id = int(parts[2])
    meeting_id = int(parts[3])
    
    async with pool.acquire() as conn:
        # Получаем информацию о пользователе
        user = await conn.fetchrow(
            '''
            SELECT id, username, name, surname, registration_date
            FROM users 
            WHERE id = $1
            ''',
            user_id
        )
    
    if not user:
        msg = await callback.message.edit_text("❌ Информация о пользователе не найдена.", reply_markup=None)
        await state.update_data(last_private_message_id=msg.message_id)
        return
    
    text = f"👤 Профиль участника:\n\n"
    text += f"{user['name']} {user['surname']}\n"
    
    if user['username']:
        text += f"Telegram: @{user['username']}\n"
    else:
        text += f"Telegram: не указан\n"
    
    if user['registration_date']:
        reg_date = user['registration_date'].strftime('%d.%m.%Y')
        text += f"В сообществе с {reg_date}\n"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="В меню", callback_data="main_menu")
    builder.adjust(1)
    
    msg = await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await state.update_data(last_private_message_id=msg.message_id)

# Универсальный обработчик возврата в главное меню из любого места
@router.callback_query(F.data == "main_menu")
async def cb_main_menu_meetings(callback: CallbackQuery, state: FSMContext):
    # Удаляем последнее "личное" сообщение, если оно есть
    data = await state.get_data()
    msg_id = data.get("last_private_message_id")
    if msg_id:
        try:
            await callback.bot.delete_message(callback.message.chat.id, msg_id)
        except Exception:
            pass
        await state.update_data(last_private_message_id=None)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.message.answer(
        "Главное меню",
        reply_markup=get_main_menu()
    )
    await state.clear()