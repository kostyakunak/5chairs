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
    """Показывает все заявки и встречи пользователя с их статусами"""
    if is_callback:
        user_id = event.from_user.id
    else:
        user_id = event.from_user.id
    try:
        applications = await get_user_applications(user_id)
        now = datetime.now()
        upcoming = []
        pending = []
        past = []
        for app in applications:
            slot_dt = None
            if app.get('meeting_date') and app.get('meeting_time'):
                slot_dt = datetime.combine(app['meeting_date'], app['meeting_time'])
            if app['status'] == 'pending':
                pending.append(app)
            elif app['status'] == 'approved':
                if slot_dt and slot_dt < now:
                    past.append(app)
                else:
                    upcoming.append(app)
            elif app['status'] == 'completed':
                past.append(app)
        text = "📅 Ваши встречи и заявки:\n\n"
        idx = 1
        for app in pending:
            text += f"{idx}. {app['city_name']}, {app['day_of_week']} {app['time'].strftime('%H:%M')}\nСтатус: на рассмотрении\n\n"
            idx += 1
        for app in upcoming:
            text += f"{idx}. {app['city_name']}, {app['day_of_week']} {app['time'].strftime('%H:%M')}\nСтатус: одобрено\n\n"
            idx += 1
        if past:
            text += "\n📜 Прошедшие встречи:\n\n"
            for app in past:
                text += f"- {app['city_name']}, {app['day_of_week']} {app['time'].strftime('%H:%M')}\n"
        builder = InlineKeyboardBuilder()
        builder.button(text="В меню", callback_data="main_menu")
        builder.adjust(1)
        if is_callback:
            msg = await event.message.edit_text(text, reply_markup=builder.as_markup())
        else:
            await event.answer("Список встреч:", reply_markup=ReplyKeyboardRemove())
            msg = await event.answer(text, reply_markup=builder.as_markup())
        await state.update_data(last_private_message_id=msg.message_id)
    except Exception as e:
        builder = InlineKeyboardBuilder()
        builder.button(text="В меню", callback_data="main_menu")
        builder.adjust(1)
        error_text = f"Ошибка при получении встреч: {str(e)}"
        if is_callback:
            msg = await event.message.edit_text(error_text, reply_markup=builder.as_markup())
        else:
            await event.answer("Список встреч:", reply_markup=ReplyKeyboardRemove())
            msg = await event.answer(error_text, reply_markup=builder.as_markup())
        await state.update_data(last_private_message_id=msg.message_id)

# Meeting details handler
@router.callback_query(F.data.startswith("meeting_details_"))
async def show_meeting_details(callback, state: FSMContext):
    meeting_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    try:
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
            builder = InlineKeyboardBuilder()
            builder.button(text="В меню", callback_data="main_menu")
            builder.adjust(1)
            msg = await callback.message.edit_text("Детали встречи не найдены.", reply_markup=builder.as_markup())
            await state.update_data(last_private_message_id=msg.message_id)
            return
        members = await get_meeting_members(meeting_id)
        details = (
            f"📅 Встреча: {meeting['name']}\n"
            f"📍 Локация: {meeting['city_name']} — {meeting['venue']}"
        )
        if meeting.get('venue_address'):
            details += f"\n📌 Адрес: {meeting['venue_address']}"
        details += (
            f"\n⏰ Дата и время: {meeting['meeting_date'].strftime('%A, %d.%m.%Y')} в {meeting['meeting_time'].strftime('%H:%M')}\n"
            f"Статус: {meeting['status'].capitalize()}\n"
        )
        if meeting.get('day_of_week') and meeting.get('start_time') and meeting.get('end_time'):
            details += f"\n⏱️ Временной слот: {meeting['day_of_week']} {meeting['start_time'].strftime('%H:%M')}-{meeting['end_time'].strftime('%H:%M')}"
        meeting_datetime = datetime.combine(meeting['meeting_date'], meeting['meeting_time'])
        now = datetime.now()
        if meeting_datetime > now:
            time_until = meeting_datetime - now
            days = time_until.days
            hours, remainder = divmod(time_until.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            details += f"\n\n⏳ До встречи: {days} дн., {hours} ч., {minutes} мин."
        details += "\n\nУчастники:\n"
        if members:
            for i, member in enumerate(members, 1):
                details += f"{i}. {member['name']} {member['surname']}\n"
        else:
            details += "Пока нет участников."
        details += (
            f"\n\n📋 Повестка встречи:\n"
            f"- Знакомство и ice-breakers (15 мин)\n"
            f"- Метод 5 стульев (10 мин)\n"
            f"- Основная дискуссия (60 мин)\n"
            f"- Завершение и выводы (15 мин)\n\n"
            f"Пожалуйста, приходите за 5-10 минут до начала!"
        )
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(
            text="Назад к встречам",
            callback_data="back_to_meetings"
        ))
        builder.button(text="В меню", callback_data="main_menu")
        builder.adjust(1)
        msg = await callback.message.edit_text(
            details,
            reply_markup=builder.as_markup()
        )
        await state.update_data(last_private_message_id=msg.message_id)
    except Exception as e:
        builder = InlineKeyboardBuilder()
        builder.button(text="В меню", callback_data="main_menu")
        builder.adjust(1)
        msg = await callback.message.edit_text(f"Ошибка при получении деталей встречи: {str(e)}", reply_markup=builder.as_markup())
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
    await show_main_menu(callback.message, state)
    await state.clear()