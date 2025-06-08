import logging
from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime

logger = logging.getLogger(__name__)

from database.db import (
    is_admin, get_application, update_application_status,
    get_user_answers, get_user, get_user_application, pool, add_meeting_member, get_meeting,
    get_city, get_pending_applications_by_city, get_pending_applications_by_timeslot, get_available_dates_by_city_and_timeslot,
    get_active_cities, update_user, init_db, get_pool, get_compatible_users_for_meeting, create_meeting
)
from config import MAX_MEETING_SIZE
from services.notification_service import NotificationService
from admin_bot.states import ApplicationReviewStates, MeetingManagementStates

# Create router
router = Router()

# Applications command handler
@router.message(Command("applications"))
async def cmd_applications(message: Message, state: FSMContext):
    # Показываем выбор города
    cities = await get_active_cities()
    if not cities:
        await message.answer("Нет активных городов.")
        return
    
    builder = InlineKeyboardBuilder()
    for city in cities:
        builder.add(InlineKeyboardButton(
            text=city['name'],
            callback_data=f"select_city_{city['id']}"
        ))
    builder.adjust(2)
    
    await message.answer(
        "Выберите город для просмотра заявок:",
        reply_markup=builder.as_markup()
    )
    
    await state.clear()

# Обработчик выбора города
@router.callback_query(F.data.startswith("select_city_"))
async def select_city_for_applications(callback: CallbackQuery, state: FSMContext):
    city_id = int(callback.data.split('_')[-1])
    await state.update_data(city_id=city_id)
    # Показываем выбор способа просмотра заявок
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="По старшинству")],
            [KeyboardButton(text="По временному слоту")],
            [KeyboardButton(text="Back to Menu")]
        ],
        resize_keyboard=True
    )
    await callback.message.answer(
        "Выберите способ просмотра заявок:",
        reply_markup=keyboard
    )
    await callback.answer()

# Обработчик для просмотра по старшинству
@router.message(F.text == "По старшинству")
async def applications_by_oldest(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    data = await state.get_data()
    city_id = data.get('city_id')
    if not city_id:
        await message.answer("Сначала выберите город через /applications.")
        return
    applications = await get_pending_applications_by_city(city_id)
    if not applications:
        await message.answer("Нет необработанных заявок в этом городе.")
        return
    applications = sorted(applications, key=lambda x: x['created_at'])
    builder = InlineKeyboardBuilder()
    for app in applications:
        # Формируем текст кнопки
        parts = []
        if app.get('created_at'):
            parts.append(app['created_at'].strftime('%d.%m.%Y'))
        if app.get('note'):
            parts.append(f"[{app['note'][:20]}]")
        parts.append(f"{app['user_name']} {app['user_surname']} - {app['city_name']} {app['day_of_week']} {app['time'].strftime('%H:%M')}")
        btn_text = ' | '.join(parts)
        builder.add(InlineKeyboardButton(
            text=btn_text,
            callback_data=f"review_app_{app['id']}"
        ))
    builder.adjust(1)
    await message.answer(
        f"Всего {len(applications)} необработанных заявок в выбранном городе. Выберите для просмотра:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(ApplicationReviewStates.select_application)

# Обработчик для просмотра по временному слоту
@router.message(F.text == "По временному слоту")
async def applications_by_timeslot(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    data = await state.get_data()
    city_id = data.get('city_id')
    if not city_id:
        await message.answer("Сначала выберите город через /applications.")
        return
    applications = await get_pending_applications_by_city(city_id)
    if not applications:
        await message.answer("Нет необработанных заявок в этом городе.")
        return
    slots = {}
    for app in applications:
        key = (app['day_of_week'], app['time'].strftime('%H:%M'))
        if key not in slots:
            slots[key] = []
        slots[key].append(app)
    builder = InlineKeyboardBuilder()
    for (day, time), apps in slots.items():
        builder.add(InlineKeyboardButton(
            text=f"{day} {time} ({len(apps)})",
            callback_data=f"slot_{day}_{time}"
        ))
    builder.adjust(1)
    await message.answer(
        "Выберите временной слот:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(ApplicationReviewStates.filter_by_time)

# Обработчик для показа заявок по выбранному временному слоту
@router.callback_query(ApplicationReviewStates.filter_by_time, F.data.startswith("slot_"))
async def show_applications_for_slot(callback: CallbackQuery, state: FSMContext):
    _, day, time = callback.data.split('_', 2)
    data = await state.get_data()
    city_id = data.get('city_id')
    # Получаем все заявки по городу
    applications = await get_pending_applications_by_city(city_id)
    # Фильтруем по дню недели и времени
    filtered = [app for app in applications if app['day_of_week'] == day and app['time'].strftime('%H:%M') == time]
    if not filtered:
        await callback.message.edit_text("Нет заявок на этот временной слот в выбранном городе.")
        return
    filtered = sorted(filtered, key=lambda x: x['created_at'])
    builder = InlineKeyboardBuilder()
    for app in filtered:
        parts = []
        if app.get('created_at'):
            parts.append(app['created_at'].strftime('%d.%m.%Y'))
        if app.get('note'):
            parts.append(f"[{app['note'][:20]}]")
        parts.append(f"{app['user_name']} {app['user_surname']} - {app['city_name']} {app['day_of_week']} {app['time'].strftime('%H:%M')}")
        btn_text = ' | '.join(parts)
        builder.add(InlineKeyboardButton(
            text=btn_text,
            callback_data=f"review_app_{app['id']}"
        ))
    builder.adjust(1)
    await callback.message.edit_text(
        f"Заявки на {day} {time} в выбранном городе:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(ApplicationReviewStates.select_application)

# Review applications handler
@router.message(F.text == "Review Applications")
async def review_applications_command(message: Message, state: FSMContext):
    try:
        if not await is_admin(message.from_user.id):
            await message.answer("У вас нет прав администратора.")
            return
        applications = await get_pending_applications_by_city(city_id)
        if not applications:
            await message.answer("Нет заявок на рассмотрение.")
            return
        grouped_apps = {}
        for app in applications:
            key = f"{app['city_name']}_{app['day_of_week']}_{app['time'].strftime('%H:%M')}"
            if key not in grouped_apps:
                grouped_apps[key] = {
                    'city_name': app['city_name'],
                    'day_of_week': app['day_of_week'],
                    'time': app['time'],
                    'apps': []
                }
            grouped_apps[key]['apps'].append(app)
        builder = InlineKeyboardBuilder()
        for app in applications:
            builder.add(InlineKeyboardButton(
                text=f"👤 {app['user_name']} {app['user_surname']}",
                callback_data=f"review_app_{app['id']}"
            ))
        for key, group in grouped_apps.items():
            if len(group['apps']) > 1:
                builder.add(InlineKeyboardButton(
                    text=f"🔄 Пакетно ({len(group['apps'])}) - {group['city_name']} {group['day_of_week']} {group['time'].strftime('%H:%M')}",
                    callback_data=f"batch_review_{key}"
                ))
        builder.adjust(1)
        await message.answer(
            f"Ожидает рассмотрения: {len(applications)} заявок. Выберите одну для просмотра или используйте пакетную обработку:",
            reply_markup=builder.as_markup()
        )
        await state.set_state(ApplicationReviewStates.select_application)
    except Exception as e:
        logger.error(f"[review_applications_command] Ошибка: {e}", exc_info=True)
        await message.answer("Произошла ошибка при получении заявок. Попробуйте ещё раз или обратитесь к разработчику.")
        await state.clear()
        return

# Application selection handler
@router.callback_query(ApplicationReviewStates.select_application, F.data.startswith("review_app_"))
async def process_application_selection(callback: CallbackQuery, state: FSMContext):
    try:
        app_id = int(callback.data.split("_")[2])
        await state.update_data(application_id=app_id)
        application = await get_application(app_id)
        if not application:
            logger.info(f"[process_application_selection] Заявка {app_id} не найдена.")
            await callback.message.edit_text("Заявка не найдена. Возможно, она была удалена.")
            await state.clear()
            return
        user = await get_user(application['user_id'])
        if not user:
            logger.info(f"[process_application_selection] Пользователь {application['user_id']} не найден для заявки {app_id}.")
            await callback.message.edit_text("Пользователь не найден. Возможно, он был удалён.")
            await state.clear()
            return
        logger.info(f"[process_application_selection] user_id={user['id']}, status={user['status']}, app_id={app_id}")
        answers = await get_user_answers(application['user_id'])
        if user['status'] != 'approved':
            logger.info(f"[process_application_selection] Первый этап модерации для user_id={user['id']}, status={user['status']}")
            details = (
                f"Пользователь: {user['name']} {user['surname']}\n"
                f"Username: @{user['username'] or 'None'}\n"
                f"Возраст: {user['age']}\n"
                f"Дата регистрации: {user['registration_date'].strftime('%d.%m.%Y')}\n\n"
                f"Ответы на вопросы:\n"
            )
            for i, answer in enumerate(answers, 1):
                details += f"{i}. {answer['question_text']}\n   Ответ: {answer['answer']}\n\n"
            builder = InlineKeyboardBuilder()
            builder.add(InlineKeyboardButton(
                text="Принять пользователя",
                callback_data=f"approve_user_{user['id']}"
            ))
            builder.add(InlineKeyboardButton(
                text="Отклонить пользователя",
                callback_data=f"reject_user_{user['id']}"
            ))
            builder.add(InlineKeyboardButton(
                text="Назад",
                callback_data="back_to_applications"
            ))
            builder.adjust(1)
            await callback.message.edit_text(
                details,
                reply_markup=builder.as_markup()
            )
            await state.set_state(ApplicationReviewStates.review_application)
            return
        logger.info(f"[process_application_selection] Второй этап модерации для user_id={user['id']}, status={user['status']}")
        details = ""
        if application.get('note'):
            details += f" [{application['note']}]\n"
        if application.get('created_at'):
            details += f"Дата подачи заявки: {application['created_at'].strftime('%d.%m.%Y')}\n"
        details += (
            f"{user['name']} {user['surname']}\n"
            f"Username: @{user['username'] or 'None'}\n"
            f"Возраст: {user['age']}\n"
            f"Город: {application['city_name']}\n"
            f"Временной слот: {application['day_of_week']} {application['time'].strftime('%H:%M')}\n\n"
            f"Ответы на вопросы:\n"
        )
        for i, answer in enumerate(answers, 1):
            details += f"{i}. {answer['question_text']}\n   Ответ: {answer['answer']}\n\n"
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(
            text="➕ В существующую встречу",
            callback_data=f"show_meetings_{app_id}"
        ))
        builder.add(InlineKeyboardButton(
            text="➕ Новая встреча",
            callback_data=f"approve_and_create_{app_id}_{application['city_id']}"
        ))
        builder.add(InlineKeyboardButton(
            text="❌ Отклонить",
            callback_data=f"reject_app_{app_id}"
        ))
        builder.add(InlineKeyboardButton(
            text="📝 Заметка",
            callback_data=f"add_notes_{app_id}"
        ))
        builder.add(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="back_to_applications"
        ))
        builder.adjust(1)
        await callback.message.edit_text(
            details,
            reply_markup=builder.as_markup()
        )
        await state.set_state(ApplicationReviewStates.review_application)
        return
    except Exception as e:
        logger.error(f"[process_application_selection] Ошибка: {e}", exc_info=True)
        await callback.message.edit_text("Произошла ошибка при обработке заявки. Попробуйте ещё раз или обратитесь к разработчику.")
        await state.clear()
        return

# Новый обработчик: показать список встреч для добавления пользователя
@router.callback_query(ApplicationReviewStates.review_application, F.data.startswith("show_meetings_"))
async def show_meetings_for_adding(callback: CallbackQuery, state: FSMContext):
    app_id = int(callback.data.split("_")[-1])
    application = await get_application(app_id)
    if not application:
        await callback.message.edit_text("Заявка не найдена.")
        await state.clear()
        return
    city_id = application['city_id']
    user_id = application['user_id']
    time_slot_id = application['time_slot_id']
    # Получаем встречи в этом городе с нужным time_slot_id
    async with pool.acquire() as conn:
        meetings = await conn.fetch('''
            SELECT m.id, m.name, m.meeting_date, m.meeting_time,
                   (SELECT COUNT(*) FROM meeting_members WHERE meeting_id = m.id) as member_count
            FROM meetings m
            JOIN meeting_time_slots mts ON m.id = mts.meeting_id
            WHERE m.city_id = $1 AND m.status = 'planned' AND mts.time_slot_id = $2
            ORDER BY m.meeting_date, m.meeting_time
        ''', city_id, time_slot_id)
        # Получаем id встреч, где пользователь уже состоит
        user_meeting_ids = set([row['meeting_id'] for row in await conn.fetch('SELECT meeting_id FROM meeting_members WHERE user_id = $1', user_id)])
    if not meetings:
        await callback.message.edit_text("Нет подходящих встреч для добавления. Создайте новую встречу.")
        return
    builder = InlineKeyboardBuilder()
    for meeting in meetings:
        if meeting['id'] in user_meeting_ids:
            continue  # Не показываем встречи, где пользователь уже состоит
        member_count = meeting['member_count']
        if member_count <= MAX_MEETING_SIZE:
            dots = '🔴' * member_count + '🟢' * (MAX_MEETING_SIZE - member_count)
        else:
            dots = '🔴' * MAX_MEETING_SIZE + f'+{member_count - MAX_MEETING_SIZE}'
        name = meeting['name']
        if len(name) > 10:
            name = name[:10] + '...'
        button_text = f"{dots} {name} ({meeting['meeting_date'].strftime('%d.%m.%Y')} {meeting['meeting_time'].strftime('%H:%M')})"
        builder.add(InlineKeyboardButton(
            text=button_text,
            callback_data=f"select_meeting_{app_id}_{meeting['id']}"
        ))
    builder.add(InlineKeyboardButton(
        text="⬅️ Назад",
        callback_data=f"review_app_{app_id}"
    ))
    builder.adjust(1)
    await callback.message.edit_text(
        "Выберите встречу для просмотра участников:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(ApplicationReviewStates.select_application)

# Новый обработчик: показать участников выбранной встречи
@router.callback_query(ApplicationReviewStates.select_application, F.data.startswith("select_meeting_"))
async def show_meeting_members_for_add(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    app_id = int(parts[2])
    meeting_id = int(parts[3])
    application = await get_application(app_id)
    if not application:
        await callback.message.edit_text("Заявка не найдена.")
        await state.clear()
        return
    async with pool.acquire() as conn:
        meeting = await conn.fetchrow('SELECT * FROM meetings WHERE id = $1', meeting_id)
        members = await conn.fetch('''
            SELECT u.id, u.name, u.surname, u.username, u.age
            FROM meeting_members mm
            JOIN users u ON mm.user_id = u.id
            WHERE mm.meeting_id = $1
            ORDER BY mm.added_at
        ''', meeting_id)
    text = (
        f"Встреча: {meeting['name']}\nДата: {meeting['meeting_date'].strftime('%d.%m.%Y')} {meeting['meeting_time'].strftime('%H:%M')}\n"
        f"Участники ({len(members)}/5):\n"
    )
    for i, member in enumerate(members, 1):
        text += f"{i}. {member['name']} {member['surname']} (@{member['username'] or '-'}), {member['age']} лет\n"
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="➕ Добавить пользователя в эту встречу",
        callback_data=f"approve_and_add_{app_id}_{meeting_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="⬅️ Назад к списку встреч",
        callback_data=f"show_meetings_{app_id}"
    ))
    builder.adjust(1)
    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup()
    )
    await state.set_state(ApplicationReviewStates.select_application)

# approve_application — только approve заявки, никаких events
@router.callback_query(ApplicationReviewStates.review_application, F.data.startswith("confirm_approve_"))
async def confirm_approve_application(callback: CallbackQuery, state: FSMContext):
    app_id = int(callback.data.split("_")[2])
    await update_application_status(app_id, "approved", None)
    await callback.message.edit_text("Заявка одобрена. Теперь вы можете добавить пользователя во встречу.")
    await state.clear()

# approve_and_add_to_meeting — approve заявки и добавить в meeting
@router.callback_query(ApplicationReviewStates.select_application, F.data.startswith("approve_and_add_"))
async def approve_and_add_to_meeting(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    app_id = int(parts[3])
    meeting_id = int(parts[4])
    application = await get_application(app_id)
    if not application:
        await callback.message.edit_text("Заявка не найдена.")
        await state.clear()
        return
    user_id = application['user_id']
    user = await get_user(user_id)
    # Обновляем статус заявки
    await update_application_status(app_id, "approved", None)
    # Добавляем пользователя во встречу
    await add_meeting_member(meeting_id, user_id)
    # Отправляем уведомление
    notification_service = NotificationService(callback.bot)
    await notification_service.send_application_status_update(user_id, "approved", None, meeting_id)
    # Получаем данные встречи для отображения
    async with pool.acquire() as conn:
        meeting = await conn.fetchrow('SELECT * FROM meetings WHERE id = $1', meeting_id)
    text = (
        f"✅ Пользователь {user['name']} {user['surname']} успешно добавлен во встречу '{meeting['name']}'!\n"
        f"Дата: {meeting['meeting_date'].strftime('%d.%m.%Y')} {meeting['meeting_time'].strftime('%H:%M')}\n"
    )
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="⬅️ К заявкам",
        callback_data="back_to_applications"
    ))
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await state.set_state(ApplicationReviewStates.select_application)

# approve_and_create_meeting — approve заявки, создать meeting, добавить пользователя
@router.callback_query(ApplicationReviewStates.review_application, F.data.startswith("approve_and_create_"))
async def approve_and_create_meeting(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    app_id = int(parts[3])
    city_id = int(parts[4])
    application = await get_application(app_id)
    if not application:
        await callback.message.edit_text("Заявка не найдена. Возможно, она была удалена.")
        await state.clear()
        return
    user = await get_user(application['user_id'])
    if not user:
        await callback.message.edit_text("Пользователь не найден. Возможно, он был удалён.")
        await state.clear()
        return
    data = await state.get_data()
    admin_notes = data.get('admin_notes', None)
    await update_application_status(app_id, "approved", admin_notes)
    # Собираем параметры для встречи
    meeting_name = data.get('meeting_name') or f"Встреча {user['name']} {user['surname']}"
    meeting_date = data.get('meeting_date') or datetime.now().date()
    meeting_time = data.get('timeslot_time') or application['time'].strftime('%H:%M')
    venue = data.get('venue_name') or "-"
    venue_address = data.get('venue_address', '')
    created_by = callback.from_user.id
    # Создаём встречу через функцию
    meeting_id = await create_meeting(
        name=meeting_name,
        meeting_date=meeting_date if not isinstance(meeting_date, str) else datetime.strptime(meeting_date, '%Y-%m-%d').date(),
        meeting_time=meeting_time if not isinstance(meeting_time, str) else datetime.strptime(meeting_time, '%H:%M').time(),
        city_id=city_id,
        venue=venue,
        created_by=created_by,
        venue_address=venue_address
    )
    # Привязываем слот к встрече
    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO meeting_time_slots (meeting_id, time_slot_id)
            VALUES ($1, $2)
        ''', meeting_id, application['time_slot_id'])
    # Добавляем пользователя в участники
    await add_meeting_member(meeting_id, user['id'], added_by=created_by)
    # Отправляем уведомление
    notification_service = NotificationService(callback.bot)
    await notification_service.send_application_status_update(user['id'], "approved", admin_notes, meeting_id)
    # Показываем результат админу
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="📋 Просмотреть созданную встречу",
        callback_data=f"view_meeting_{meeting_id}"
    ))
    builder.adjust(1)
    await callback.message.edit_text(
        f"✅ Встреча '{meeting_name}' успешно создана!\n\n"
        f"Участник {user['name']} {user['surname']} добавлен в встречу и уведомлён.",
        reply_markup=builder.as_markup()
    )
    await state.clear()
    await callback.answer()

# batch_review_callback — только по applications
@router.callback_query(ApplicationReviewStates.select_application, F.data.startswith("batch_review_"))
async def batch_review_callback(callback: CallbackQuery, state: FSMContext):
    key = callback.data[len("batch_review_"):]
    city_name, day_of_week, time = key.rsplit('_', 2)
    applications = await get_pending_applications_by_city(city_name)
    batch_apps = [app for app in applications if app['day_of_week'] == day_of_week and app['time'].strftime('%H:%M') == time]
    if not batch_apps:
        await callback.message.edit_text("Нет заявок для пакетной обработки по выбранному критерию.")
        await state.clear()
        return
    builder = InlineKeyboardBuilder()
    for app in batch_apps:
        builder.add(InlineKeyboardButton(
            text=f"👤 {app['user_name']} {app['user_surname']}",
            callback_data=f"review_app_{app['id']}"
        ))
    builder.add(InlineKeyboardButton(
        text="⬅️ Назад",
        callback_data="back_to_applications"
    ))
    builder.adjust(1)
    await callback.message.edit_text(
        f"Пакетная обработка заявок: {city_name}, {day_of_week} {time}\n\nВыберите заявку для просмотра:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(ApplicationReviewStates.select_application)

# reject_application_callback — только applications
@router.callback_query(ApplicationReviewStates.review_application, F.data.startswith("reject_app_"))
async def reject_application_callback(callback: CallbackQuery, state: FSMContext):
    app_id = int(callback.data.split('_')[-1])
    await update_application_status(app_id, "rejected", None)
    await callback.message.edit_text("Заявка отклонена и больше не будет отображаться в списке.")
    await state.clear()

# add_notes_callback и process_admin_note — только applications
@router.callback_query(ApplicationReviewStates.review_application, F.data.startswith("add_notes_"))
async def add_notes_callback(callback: CallbackQuery, state: FSMContext):
    app_id = int(callback.data.split('_')[-1])
    await state.update_data(application_id=app_id)
    await callback.message.edit_text("Пожалуйста, введите текст заметки для этой заявки:")
    await state.set_state(ApplicationReviewStates.enter_admin_note)

@router.message(ApplicationReviewStates.enter_admin_note)
async def process_admin_note(message: Message, state: FSMContext):
    note = message.text.strip()
    if not note:
        await message.answer("Заметка не может быть пустой. Пожалуйста, введите текст заметки:")
        return
    data = await state.get_data()
    app_id = data.get('application_id')
    await update_application_status(app_id, None, note)  # только заметка
    await message.answer("Заметка сохранена! Возвращаюсь к заявке...")
    # Вместо fake_callback просто повторно показываем заявку
    # Получаем заявку и пользователя
    application = await get_application(app_id)
    if not application:
        await message.answer("Заявка не найдена. Возможно, она была удалена.")
        await state.clear()
        return
    user = await get_user(application['user_id'])
    if not user:
        await message.answer("Пользователь не найден. Возможно, он был удалён.")
        await state.clear()
        return
    answers = await get_user_answers(application['user_id'])
    details = (
        f"Заявка от {user['name']} {user['surname']}\n"
        f"Username: @{user['username'] or 'None'}\n"
        f"Возраст: {user['age']}\n"
        f"Дата регистрации: {user['registration_date'].strftime('%d.%m.%Y')}\n\n"
        f"Город: {application['city_name']}\n"
        f"Временной слот: {application['day_of_week']} {application['time'].strftime('%H:%M')}\n\n"
        f"Ответы на вопросы:\n"
    )
    for i, answer in enumerate(answers, 1):
        details += f"{i}. {answer['question_text']}\n   Ответ: {answer['answer']}\n\n"
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="➕ В существующую встречу",
        callback_data=f"show_meetings_{app_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="➕ Новая встреча",
        callback_data=f"approve_and_create_{app_id}_{application['city_id']}"
    ))
    builder.add(InlineKeyboardButton(
        text="❌ Отклонить",
        callback_data=f"reject_app_{app_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="📝 Заметка",
        callback_data=f"add_notes_{app_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="⬅️ Назад",
        callback_data="back_to_applications"
    ))
    builder.adjust(1)
    await message.answer(details, reply_markup=builder.as_markup())
    await state.set_state(ApplicationReviewStates.review_application)

# Обработчик для кнопки "Одобрить и добавить в существующую встречу"
@router.callback_query(ApplicationReviewStates.review_application, F.data.startswith("approve_and_add_"))
async def approve_and_add_to_meeting(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    app_id = int(parts[3])
    meeting_id = int(parts[4])
    application = await get_application(app_id)
    if not application:
        await callback.message.edit_text("Заявка не найдена.")
        await state.clear()
        return
    user_id = application['user_id']
    # Обновляем статус заявки
    await update_application_status(app_id, "approved", None)
    # Добавляем пользователя во встречу
    await add_meeting_member(meeting_id, user_id)
    # Отправляем уведомление
    notification_service = NotificationService(callback.bot)
    await notification_service.send_application_status_update(user_id, "approved", None, meeting_id)
    # Получаем данные встречи для отображения
    async with pool.acquire() as conn:
        meeting = await conn.fetchrow('SELECT * FROM meetings WHERE id = $1', meeting_id)
    text = (
        f"✅ Пользователь {user['name']} {user['surname']} успешно добавлен во встречу '{meeting['name']}'!\n"
        f"Дата: {meeting['meeting_date'].strftime('%d.%m.%Y')} {meeting['meeting_time'].strftime('%H:%M')}\n"
    )
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="⬅️ К заявкам",
        callback_data="back_to_applications"
    ))
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await state.set_state(ApplicationReviewStates.select_application)

# Обработчик для кнопки "Одобрить и создать новую встречу"
@router.callback_query(ApplicationReviewStates.review_application, F.data.startswith("approve_and_create_"))
async def approve_and_create_meeting(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    app_id = int(parts[3])
    city_id = int(parts[4])
    application = await get_application(app_id)
    if not application:
        await callback.message.edit_text("Заявка не найдена. Возможно, она была удалена.")
        await state.clear()
        return
    user = await get_user(application['user_id'])
    if not user:
        await callback.message.edit_text("Пользователь не найден. Возможно, он был удалён.")
        await state.clear()
        return
    data = await state.get_data()
    admin_notes = data.get('admin_notes', None)
    await update_application_status(app_id, "approved", admin_notes)
    # Собираем параметры для встречи
    meeting_name = data.get('meeting_name') or f"Встреча {user['name']} {user['surname']}"
    meeting_date = data.get('meeting_date') or datetime.now().date()
    meeting_time = data.get('timeslot_time') or application['time'].strftime('%H:%M')
    venue = data.get('venue_name') or "-"
    venue_address = data.get('venue_address', '')
    created_by = callback.from_user.id
    # Создаём встречу через функцию
    meeting_id = await create_meeting(
        name=meeting_name,
        meeting_date=meeting_date if not isinstance(meeting_date, str) else datetime.strptime(meeting_date, '%Y-%m-%d').date(),
        meeting_time=meeting_time if not isinstance(meeting_time, str) else datetime.strptime(meeting_time, '%H:%M').time(),
        city_id=city_id,
        venue=venue,
        created_by=created_by,
        venue_address=venue_address
    )
    # Привязываем слот к встрече
    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO meeting_time_slots (meeting_id, time_slot_id)
            VALUES ($1, $2)
        ''', meeting_id, application['time_slot_id'])
    # Добавляем пользователя в участники
    await add_meeting_member(meeting_id, user['id'], added_by=created_by)
    # Отправляем уведомление
    notification_service = NotificationService(callback.bot)
    await notification_service.send_application_status_update(user['id'], "approved", admin_notes, meeting_id)
    # Показываем результат админу
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="📋 Просмотреть созданную встречу",
        callback_data=f"view_meeting_{meeting_id}"
    ))
    builder.adjust(1)
    await callback.message.edit_text(
        f"✅ Встреча '{meeting_name}' успешно создана!\n\n"
        f"Участник {user['name']} {user['surname']} добавлен в встречу и уведомлён.",
        reply_markup=builder.as_markup()
    )
    await state.clear()
    await callback.answer()

# Обработчик выбора даты для новой встречи
@router.callback_query(ApplicationReviewStates.choose_meeting_date, F.data.startswith("create_meeting_date_"))
async def choose_meeting_date(callback: CallbackQuery, state: FSMContext):
    # Извлекаем выбранную дату
    selected_date = callback.data.split("_")[3]
    
    # Сохраняем дату в state
    await state.update_data(meeting_date=selected_date)
    
    # Получаем данные из state
    data = await state.get_data()
    
    await callback.message.edit_text(
        f"Вы выбрали дату: {selected_date}\n\n"
        f"Введите название для новой встречи с участником {data['user_name']}:"
    )
    
    # Устанавливаем состояние ввода названия встречи
    await state.set_state(ApplicationReviewStates.enter_meeting_name)

# Обработчик ввода названия встречи
@router.message(ApplicationReviewStates.enter_meeting_name)
async def enter_meeting_name(message: Message, state: FSMContext):
    # Сохраняем название встречи
    meeting_name = message.text.strip()
    
    if not meeting_name:
        await message.answer("Пожалуйста, введите корректное название для встречи.")
        return
    
    await state.update_data(meeting_name=meeting_name)
    
    # Получаем данные из state
    data = await state.get_data()
    
    # Предлагаем выбрать место проведения
    builder = InlineKeyboardBuilder()
    
    # Получаем список мест проведения в выбранном городе
    async with pool.acquire() as conn:
        venues = await conn.fetch('''
            SELECT id, name, address
            FROM venues
            WHERE city_id = $1 AND active = true
            ORDER BY name
        ''', data['city_id'])
    
    if not venues:
        # Если нет мест проведения, предлагаем ввести вручную
        await message.answer(
            f"В городе {data['city_name']} нет сохраненных мест проведения.\n\n"
            f"Пожалуйста, введите место проведения для встречи:"
        )
        await state.set_state(ApplicationReviewStates.enter_venue_manually)
        return
    
    # Создаем клавиатуру с местами проведения
    for venue in venues:
        builder.add(InlineKeyboardButton(
            text=venue['name'],
            callback_data=f"select_venue_{venue['id']}"
        ))
    
    # Опция ввести место проведения вручную
    builder.add(InlineKeyboardButton(
        text="Ввести вручную",
        callback_data="enter_venue_manually"
    ))
    
    builder.add(InlineKeyboardButton(
        text="Отмена",
        callback_data="cancel_meeting_creation"
    ))
    
    builder.adjust(1)
    
    await message.answer(
        f"Название встречи: {meeting_name}\n\n"
        f"Выберите место проведения для встречи:",
        reply_markup=builder.as_markup()
    )

    # Устанавливаем состояние выбора места проведения
    await state.set_state(ApplicationReviewStates.choose_venue)

# Обработчик выбора места проведения
@router.callback_query(ApplicationReviewStates.choose_venue, F.data.startswith("select_venue_"))
async def select_venue(callback: CallbackQuery, state: FSMContext):
    # Извлекаем ID выбранного места
    venue_id = int(callback.data.split("_")[2])
    
    # Получаем информацию о месте проведения
    async with pool.acquire() as conn:
        venue = await conn.fetchrow('''
            SELECT id, name, address
            FROM venues
            WHERE id = $1
        ''', venue_id)
    
    if not venue:
        await callback.message.edit_text("Выбранное место проведения не найдено. Пожалуйста, выберите другое.")
        return
    
    # Сохраняем информацию о месте проведения
    await state.update_data(
        venue_id=venue['id'],
        venue_name=venue['name'],
        venue_address=venue['address']
    )
    
    # Переходим к подтверждению создания встречи
    await show_meeting_confirmation(callback.message, state)
    await callback.answer()

# Обработчик для ручного ввода места проведения
@router.callback_query(ApplicationReviewStates.choose_venue, F.data == "enter_venue_manually")
async def enter_venue_manually_callback(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Пожалуйста, введите название места проведения встречи:")
    await state.set_state(ApplicationReviewStates.enter_venue_manually)
    await callback.answer()

# Обработчик ручного ввода места проведения
@router.message(ApplicationReviewStates.enter_venue_manually)
async def process_manual_venue(message: Message, state: FSMContext):
    venue_name = message.text.strip()
    
    if not venue_name:
        await message.answer("Пожалуйста, введите корректное название места проведения.")
        return
    
    await state.update_data(venue_name=venue_name, venue_address="")
    
    await message.answer("Теперь введите адрес места проведения (или '-', если не требуется):")
    await state.set_state(ApplicationReviewStates.enter_venue_address)

# Обработчик ввода адреса места проведения
@router.message(ApplicationReviewStates.enter_venue_address)
async def process_venue_address(message: Message, state: FSMContext):
    venue_address = message.text.strip()
    
    if venue_address == '-':
        venue_address = ""
    
    await state.update_data(venue_address=venue_address)
    
    # Переходим к подтверждению создания встречи
    await show_meeting_confirmation(message, state)

# Функция отображения подтверждения создания встречи
async def show_meeting_confirmation(message: Message, state: FSMContext):
    data = await state.get_data()
    
    # Формируем информацию о встрече для подтверждения
    meeting_info = (
        f"Информация о новой встрече:\n\n"
        f"Название: {data['meeting_name']}\n"
        f"Город: {data['city_name']}\n"
        f"Дата: {data['meeting_date']}\n"
        f"День недели: {data['timeslot_day']}\n"
        f"Время: {data['timeslot_time']}\n"
        f"Место: {data['venue_name']}"
    )
    
    if data.get('venue_address'):
        meeting_info += f"\nАдрес: {data['venue_address']}"
    
    meeting_info += f"\n\nУчастник: {data['user_name']}"
    
    # Создаем клавиатуру подтверждения
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="✅ Создать встречу",
        callback_data="confirm_create_meeting"
    ))
    builder.add(InlineKeyboardButton(
        text="❌ Отмена",
        callback_data="cancel_meeting_creation"
    ))
    builder.adjust(1)
    
    await message.answer(
        f"{meeting_info}\n\n"
        f"Подтвердите создание встречи:",
        reply_markup=builder.as_markup()
    )
    
    # Устанавливаем состояние подтверждения создания встречи
    await state.set_state(ApplicationReviewStates.confirm_meeting_creation)

# Обработчик подтверждения создания встречи
@router.callback_query(ApplicationReviewStates.confirm_meeting_creation, F.data == "confirm_create_meeting")
async def confirm_create_meeting(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    try:
        async with pool.acquire() as conn:
            venue_id = data.get('venue_id')
            if not venue_id:
                venue_result = await conn.fetchrow('''
                    INSERT INTO venues (name, address, city_id, active)
                    VALUES ($1, $2, $3, true)
                    RETURNING id
                ''', data['venue_name'], data.get('venue_address', ''), data['city_id'])
                venue_id = venue_result['id']
            meeting_result = await conn.fetchrow('''
                INSERT INTO meetings (
                    name, city_id, meeting_date, meeting_time, 
                    venue, venue_address, status, created_by, created_at
                )
                VALUES (
                    $1, $2, $3, $4, $5, $6, 'planned', $7, NOW()
                )
                RETURNING id
            ''', 
            data['meeting_name'], 
            data['city_id'], 
            datetime.strptime(data['meeting_date'], '%Y-%m-%d').date() if isinstance(data['meeting_date'], str) else data['meeting_date'], 
            datetime.strptime(data['timeslot_time'], '%H:%M').time(), 
            data['venue_name'],
            data.get('venue_address', ''),
            callback.from_user.id)
            meeting_id = meeting_result['id']
            await conn.execute('''
                INSERT INTO meeting_time_slots (meeting_id, time_slot_id)
                VALUES ($1, $2)
            ''', meeting_id, data['time_slot_id'])
            await conn.execute('''
                INSERT INTO meeting_members (meeting_id, user_id, added_by, added_at, status)
                VALUES ($1, $2, $3, NOW(), 'confirmed')
            ''', meeting_id, data['user_id'], callback.from_user.id)
            logger.info(f"[confirm_create_meeting] Создана новая встреча meeting_id={meeting_id} с пользователем user_id={data['user_id']}")
        notification_service = NotificationService(callback.bot)
        try:
            await notification_service.send_meeting_invitation(data['user_id'], meeting_id)
            logger.info(f"[confirm_create_meeting] Уведомление о встрече отправлено пользователю user_id={data['user_id']}")
        except Exception as e:
            logger.error(f"[confirm_create_meeting] Ошибка отправки уведомления о встрече: {e}")
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(
            text="📋 Просмотреть созданную встречу",
            callback_data=f"view_meeting_{meeting_id}"
        ))
        builder.adjust(1)
        await callback.message.edit_text(
            f"✅ Встреча '{data['meeting_name']}' успешно создана!\n\n"
            f"Участник {data['user_name']} добавлен в встречу и уведомлён.",
            reply_markup=builder.as_markup()
        )
    except Exception as e:
        logger.error(f"[confirm_create_meeting] Ошибка при создании встречи: {e}", exc_info=True)
        await callback.message.edit_text(
            f"❌ Произошла ошибка при создании встречи: {str(e)}\n\n"
            f"Пожалуйста, попробуйте позже или создайте встречу через меню управления встречами."
        )
    await state.clear()
    await callback.answer()

# Обработчик отмены создания встречи
@router.callback_query(F.data == "cancel_meeting_creation")
async def cancel_meeting_creation(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Создание встречи отменено. Пользователь остается одобренным, но не добавлен в встречу."
    )
    await state.clear()
    await callback.answer()

# Обработчик для просмотра созданной встречи
@router.callback_query(F.data.startswith("view_meeting_"))
async def view_meeting(callback: CallbackQuery, state: FSMContext):
    meeting_id = int(callback.data.split("_")[2])
    meeting = await get_meeting(meeting_id)
    if not meeting:
        await callback.message.edit_text("Встреча не найдена.")
        return
    # Получаем список участников встречи
    pool_obj = await get_pool()
    async with pool_obj.acquire() as conn:
        members = await conn.fetch('''
            SELECT u.id, u.name, u.surname, u.username, u.age
            FROM meeting_members mm
            JOIN users u ON mm.user_id = u.id
            WHERE mm.meeting_id = $1
            ORDER BY mm.added_at
        ''', meeting_id)
    # Форматируем информацию о встрече
    city_name = meeting.get('city_name') or meeting.get('city', {}).get('name', '-')
    venue = meeting.get('venue') or (meeting.get('venue', {}).get('name') if isinstance(meeting.get('venue'), dict) else '-')
    meeting_info = (
        f"📋 Информация о встрече:\n\n"
        f"Название: {meeting['name']}\n"
        f"Город: {city_name}\n"
        f"Дата: {meeting['meeting_date'].strftime('%d.%m.%Y')}\n"
        f"Время: {meeting['meeting_time'].strftime('%H:%M')}\n"
        f"Место: {venue}\n"
        f"Статус: {meeting['status']}\n\n"
        f"👥 Участники ({len(members)}/{MAX_MEETING_SIZE}):\n"
    )
    for i, member in enumerate(members, 1):
        meeting_info += f"{i}. {member['name']} {member['surname']}"
        if member['username']:
            meeting_info += f" (@{member['username']})"
        meeting_info += f" - {member['age']} лет\n"
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="⬅️ К заявкам",
        callback_data="back_to_applications"
    ))
    builder.adjust(1)
    await callback.message.edit_text(
        meeting_info,
        reply_markup=builder.as_markup()
    )
    await callback.answer()

# Обработчик для добавления дополнительных участников в встречу
@router.callback_query(F.data.startswith("add_more_members_"))
async def add_more_members(callback: CallbackQuery, state: FSMContext):
    meeting_id = int(callback.data.split("_")[3])
    
    # Получаем информацию о встрече
    meeting = await get_meeting(meeting_id)
    
    if not meeting:
        await callback.message.edit_text("Встреча не найдена.")
        return
    
    # Сохраняем ID встречи в state
    await state.update_data(meeting_id=meeting_id)
    
    # Получаем список подходящих пользователей
    compatible_users = await get_compatible_users_for_meeting(meeting_id)
    
    if not compatible_users:
        await callback.message.edit_text(
            f"Нет подходящих пользователей для добавления в встречу '{meeting['name']}'.\n\n"
            f"Попробуйте просмотреть другие заявки или вернуться позже."
        )
        return
    
    # Создаем клавиатуру с подходящими пользователями
    builder = InlineKeyboardBuilder()
    
    for user in compatible_users:
        builder.add(InlineKeyboardButton(
            text=f"{user['name']} {user['surname']} - {user['age']} лет",
            callback_data=f"add_user_to_meeting_{user['id']}_{meeting_id}"
        ))
    
    builder.add(InlineKeyboardButton(
        text="Назад",
        callback_data=f"view_meeting_{meeting_id}"
    ))
    
    builder.adjust(1)
    
    await callback.message.edit_text(
        f"Выберите пользователя для добавления в встречу '{meeting['name']}':",
        reply_markup=builder.as_markup()
    )
    
    # Устанавливаем состояние выбора пользователя
    await state.set_state(ApplicationReviewStates.select_user_for_meeting)
    await callback.answer()

# Обработчик выбора пользователя для добавления в встречу
@router.callback_query(ApplicationReviewStates.select_user_for_meeting, F.data.startswith("add_user_to_meeting_"))
async def confirm_add_user_to_meeting(callback: CallbackQuery, state: FSMContext):
    try:
        parts = callback.data.split("_")
        user_id = int(parts[4])
        meeting_id = int(parts[5])
        user = await get_user(user_id)
        meeting = await get_meeting(meeting_id)
        if not user or not meeting:
            await callback.message.edit_text("Пользователь или встреча не найдены.")
            await state.clear()
            return
        try:
            await add_meeting_member(meeting_id, user_id, added_by=callback.from_user.id)
            notification_service = NotificationService(callback.bot)
            await notification_service.send_meeting_invitation(user_id, meeting_id)
            builder = InlineKeyboardBuilder()
            builder.add(InlineKeyboardButton(
                text="⬅️ К заявкам",
                callback_data="back_to_applications"
            ))
            builder.adjust(1)
            await callback.message.edit_text(
                f"✅ Пользователь {user['name']} {user['surname']} успешно добавлен в встречу '{meeting['name']}'!",
                reply_markup=builder.as_markup()
            )
        except Exception as e:
            logger.error(f"[confirm_add_user_to_meeting] Ошибка при добавлении пользователя в встречу: {e}", exc_info=True)
            await callback.message.edit_text(
                f"❌ Произошла ошибка при добавлении пользователя в встречу: {str(e)}"
            )
        await state.clear()
        await callback.answer()
    except Exception as e:
        logger.error(f"[confirm_add_user_to_meeting] Критическая ошибка: {e}", exc_info=True)
        await callback.message.edit_text(
            "Произошла ошибка при добавлении пользователя во встречу. Попробуйте ещё раз или обратитесь к разработчику."
        )
        await state.clear()
        return

# Handle filter by time button
@router.callback_query(F.data == "filter_by_time")
async def filter_by_time_callback(callback: CallbackQuery, state: FSMContext):
    """Handle filter by time button callback"""
    await state.clear()
    
    # Call the filter_by_time_command function
    message = callback.message
    message.from_user = callback.from_user
    await filter_by_time_command(message, state)

# Новый обработчик для approve_user и reject_user
@router.callback_query(ApplicationReviewStates.review_application, F.data.startswith("approve_user_"))
async def approve_user_callback(callback: CallbackQuery, state: FSMContext):
    try:
        user_id = int(callback.data.split('_')[-1])
        logger.info(f"[approve_user_callback] Подтверждение пользователя user_id={user_id}")
        await update_user(user_id, status='approved')
        logger.info(f"[approve_user_callback] Статус пользователя user_id={user_id} обновлён на 'approved'")
        await callback.answer("Пользователь одобрен! Теперь можно работать с его заявками.", show_alert=True)
        data = await state.get_data()
        app_id = data.get('application_id')
        if app_id:
            logger.info(f"[approve_user_callback] Перезапуск просмотра заявки app_id={app_id} для user_id={user_id}")
            from aiogram.types import CallbackQuery as CQ
            new_callback_data = f"review_app_{app_id}"
            new_callback = CQ(
                id=callback.id,
                from_user=callback.from_user,
                chat_instance=callback.chat_instance,
                message=callback.message,
                data=new_callback_data,
                inline_message_id=None
            )
            await state.set_state(ApplicationReviewStates.select_application)
            await process_application_selection(new_callback, state)
        else:
            await callback.message.edit_text("Пользователь одобрен. Заявка не найдена, возможно была удалена.")
    except Exception as e:
        logger.error(f"[approve_user_callback] Ошибка: {e}", exc_info=True)
        await callback.message.edit_text(
            "Произошла ошибка при одобрении пользователя. Попробуйте ещё раз или обратитесь к разработчику."
        )
        await state.clear()
        return

@router.callback_query(ApplicationReviewStates.review_application, F.data.startswith("reject_user_"))
async def reject_user_callback(callback: CallbackQuery, state: FSMContext):
    try:
        user_id = int(callback.data.split('_')[-1])
        logger.info(f"[reject_user_callback] Отклонение пользователя user_id={user_id}")
        await update_user(user_id, status='rejected')
        logger.info(f"[reject_user_callback] Статус пользователя user_id={user_id} обновлён на 'rejected'")
        await callback.message.edit_text("Пользователь отклонён и больше не будет отображаться в списке.")
        await state.clear()
    except Exception as e:
        logger.error(f"[reject_user_callback] Ошибка: {e}", exc_info=True)
        await callback.message.edit_text(
            "Произошла ошибка при отклонении пользователя. Попробуйте ещё раз или обратитесь к разработчику."
        )
        await state.clear()
        return

@router.callback_query(ApplicationReviewStates.review_application, F.data.startswith("reject_app_"))
async def reject_application_callback(callback: CallbackQuery, state: FSMContext):
    try:
        app_id = int(callback.data.split('_')[-1])
        logger.info(f"[reject_application_callback] Отклонение заявки app_id={app_id}")
        # Обновляем статус заявки на 'rejected'
        await update_application_status(app_id, "rejected", None)
        logger.info(f"[reject_application_callback] Статус заявки app_id={app_id} обновлён на 'rejected'")
        await callback.message.edit_text("Заявка отклонена и больше не будет отображаться в списке.")
        await state.clear()
    except Exception as e:
        logger.error(f"[reject_application_callback] Ошибка: {e}", exc_info=True)
        await callback.message.edit_text(
            "Произошла ошибка при отклонении заявки. Попробуйте ещё раз или обратитесь к разработчику."
        )
        await state.clear()
        return

def back_to_application_kb(app_id):
    """Create a keyboard with a back button to application view"""
    kb = InlineKeyboardBuilder()
    kb.button(text="← Назад", callback_data=f"view_application_{app_id}")
    return kb.as_markup()

# Обработчик для продолжения с сегодняшней датой
@router.callback_query(F.data.startswith("use_today_date_"))
async def use_today_date(callback: CallbackQuery, state: FSMContext):
    app_id = int(callback.data.split("_")[3])
    
    # Получаем данные заявки
    application = await get_application(app_id)
    if not application:
        await callback.message.edit_text("Заявка не найдена.")
        return
    
    # Получаем информацию о пользователе
    user = await get_user(application['user_id'])
    if not user:
        await callback.message.edit_text("Пользователь не найден.")
        return
        
    # Получаем информацию о городе
    city = await get_city(application['city_id'])
    if not city:
        await callback.message.edit_text("Город не найден.")
        return
        
    # Сохраняем все необходимые данные
    today = datetime.now().date()
    await state.update_data(
        meeting_date=today,
        user_id=user['id'], 
        city_id=city['id'], 
        app_id=app_id, 
        city_name=city['name'],
        user_name=f"{user['name']} {user['surname']}",
        time_slot_id=application['time_slot_id'],
        timeslot_day=application['day_of_week'],
        timeslot_time=application['time'].strftime('%H:%M')
    )
    
    # Переходим к вводу названия встречи
    await callback.message.edit_text(
        f"Создаём встречу на сегодня ({today.strftime('%d.%m.%Y')}) для пользователя {user['name']} {user['surname']}.\n\n"
        f"Пожалуйста, введите название встречи:",
        reply_markup=back_to_application_kb(app_id)
    )
    
    # Устанавливаем состояние ввода названия встречи
    await state.set_state(ApplicationReviewStates.enter_meeting_name)
    await callback.answer()

# Обработчик для выбора другого временного слота
@router.callback_query(F.data.startswith("select_another_timeslot_"))
async def select_another_timeslot(callback: CallbackQuery, state: FSMContext):
    app_id = int(callback.data.split("_")[3])
    
    # Получаем список всех активных временных слотов
    async with pool.acquire() as conn:
        timeslots = await conn.fetch('''
            SELECT * FROM timeslots
            WHERE active = true
            ORDER BY CASE
                WHEN day_of_week = 'Monday' THEN 1
                WHEN day_of_week = 'Tuesday' THEN 2
                WHEN day_of_week = 'Wednesday' THEN 3
                WHEN day_of_week = 'Thursday' THEN 4
                WHEN day_of_week = 'Friday' THEN 5
                WHEN day_of_week = 'Saturday' THEN 6
                WHEN day_of_week = 'Sunday' THEN 7
            END, time
        ''')
    
    if not timeslots:
        await callback.message.edit_text(
            "Нет доступных временных слотов. Пожалуйста, сначала создайте временные слоты."
        )
        return
    
    # Создаем клавиатуру для выбора временного слота
    kb = InlineKeyboardBuilder()
    
    for slot in timeslots:
        slot_time = slot['time'].strftime('%H:%M')
        kb.button(
            text=f"{slot['day_of_week']}, {slot_time}",
            callback_data=f"set_timeslot_{app_id}_{slot['id']}"
        )
    
    kb.button(text="← Назад", callback_data=f"view_application_{app_id}")
    kb.adjust(1)  # Один слот в строке
    
    await callback.message.edit_text(
        "Выберите новый временной слот для создания встречи:",
        reply_markup=kb.as_markup()
    )
    await callback.answer()

# Обработчик выбора нового временного слота
@router.callback_query(F.data.startswith("set_timeslot_"))
async def set_new_timeslot(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    app_id = int(parts[2])
    time_slot_id = int(parts[3])
    
    # Получаем данные заявки
    application = await get_application(app_id)
    if not application:
        await callback.message.edit_text("Заявка не найдена.")
        return
    
    # Получаем информацию о временном слоте
    async with pool.acquire() as conn:
        timeslot = await conn.fetchrow('SELECT * FROM timeslots WHERE id = $1', time_slot_id)
    
    if not timeslot:
        await callback.message.edit_text("Выбранный временной слот не найден.")
        return
    
    # Обновляем event с новым временным слотом
    async with pool.acquire() as conn:
        # Получаем event_id из event_application
        event_id = application['event_id']
        
        # Обновляем event с новым time_slot_id
        await conn.execute('''
            UPDATE events 
            SET time_slot_id = $1
            WHERE id = $2
        ''', time_slot_id, event_id)
    
    # Получаем обновленную заявку
    updated_app = await get_application(app_id)
    
    # Продолжаем с созданием встречи для нового временного слота
    await callback.message.edit_text(
        f"Временной слот заявки обновлен на {timeslot['day_of_week']}, {timeslot['time'].strftime('%H:%M')}.\n\n"
        f"Теперь давайте создадим встречу. Получаем доступные даты..."
    )
    
    # Повторно вызываем функцию создания встречи с обновленной заявкой
    # Создаем новый callback с данными для approve_and_create_meeting
    from aiogram.types import CallbackQuery as CQ
    new_callback_data = f"approve_and_create_{app_id}_{application['city_id']}"
    new_callback = CQ(
        id=callback.id,
        from_user=callback.from_user,
        chat_instance=callback.chat_instance,
        message=callback.message,
        data=new_callback_data,
        inline_message_id=None
    )
    
    # Вызываем обработчик создания встречи с новым callback
    await approve_and_create_meeting(new_callback, state)

# Function to register handlers with the dispatcher
def register_applications_handlers(dp):
    dp.include_router(router)

@router.callback_query(F.data == "back_to_applications")
async def back_to_applications_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await cmd_applications(callback.message, state)
    await callback.answer()