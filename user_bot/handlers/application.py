import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.db import get_active_cities, get_active_timeslots, get_or_create_application, get_user_application, pool, get_user

# Импорт функций для работы с БД (заглушки, реализовать позже)
# from database.db import get_cities, get_time_slots, create_application, get_user_application, cancel_application

logger = logging.getLogger(__name__)
router = Router()

# Состояния FSM для подачи заявки
class ApplicationStates(StatesGroup):
    select_city = State()
    select_timeslot = State()
    confirm = State()
    status = State()

# Вспомогательная функция для отмены заявки
async def cancel_application(user_id):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE applications SET status = 'cancelled' WHERE user_id = $1 AND status = 'pending'
        """, user_id)

# Старт подачи заявки
@router.message(F.text == "📝 Подать заявку")
async def start_application(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user = await get_user(user_id)
    if not user:
        await message.answer("Вы не зарегистрированы. Пожалуйста, пройдите регистрацию через /start.")
        return
    if user["status"] != "approved":
        await message.answer("Ваша регистрация ещё не одобрена администратором. Ожидайте подтверждения.")
        return
    try:
        cities = await get_active_cities()
        if not cities:
            builder = InlineKeyboardBuilder()
            builder.button(text="В меню", callback_data="app_back_main")
            builder.adjust(1)
            await message.answer("Нет доступных городов для подачи заявки.", reply_markup=builder.as_markup())
            return
        builder = InlineKeyboardBuilder()
        for city in cities:
            builder.button(text=city["name"], callback_data=f"app_city_{city['id']}")
        builder.button(text="⬅️ Назад", callback_data="app_back_main")
        builder.adjust(1)
        await message.answer("Выберите город:", reply_markup=builder.as_markup())
        await state.set_state(ApplicationStates.select_city)
    except Exception as e:
        logger.error(f"Ошибка при получении городов: {e}")
        await message.answer("Ошибка при получении списка городов. Попробуйте позже.")

# Выбор города
@router.callback_query(ApplicationStates.select_city, F.data.startswith("app_city_"))
async def select_city(callback: CallbackQuery, state: FSMContext):
    city_id = int(callback.data.split("_")[-1])
    await state.update_data(city_id=city_id)
    try:
        timeslots = await get_active_timeslots()
        # Фильтруем по выбранному городу
        filtered = [ts for ts in timeslots if ts["city_id"] == city_id]
        if not filtered:
            builder = InlineKeyboardBuilder()
            builder.button(text="В меню", callback_data="app_back_main")
            builder.adjust(1)
            await callback.message.edit_text("Нет доступных временных слотов для этого города.", reply_markup=builder.as_markup())
            return
        builder = InlineKeyboardBuilder()
        for slot in filtered:
            label = f"{slot['day_of_week']} {slot['start_time'].strftime('%H:%M')}"
            builder.button(text=label, callback_data=f"app_slot_{slot['id']}")
        builder.button(text="⬅️ Назад", callback_data="app_back_city")
        builder.adjust(1)
        await callback.message.edit_text("Выберите удобное время:", reply_markup=builder.as_markup())
        await state.set_state(ApplicationStates.select_timeslot)
    except Exception as e:
        logger.error(f"Ошибка при получении слотов: {e}")
        await callback.message.edit_text("Ошибка при получении временных слотов. Попробуйте позже.")

# Кнопка "В меню" из любого состояния FSM подачи заявки
@router.callback_query(F.data == "app_back_main")
async def back_to_main_from_anywhere(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Главное меню. Выберите действие.")
    await state.clear()
    # Здесь можно вызвать главное меню или отправить клавиатуру меню

# Выбор временного слота
@router.callback_query(ApplicationStates.select_timeslot, F.data.startswith("app_slot_"))
async def select_timeslot(callback: CallbackQuery, state: FSMContext):
    slot_id = int(callback.data.split("_")[-1])
    await state.update_data(timeslot_id=slot_id)
    builder = InlineKeyboardBuilder()
    builder.button(text="Подтвердить заявку", callback_data="app_confirm")
    builder.button(text="⬅️ Назад", callback_data="app_back_slot")
    builder.adjust(1)
    await callback.message.edit_text("Подтвердите подачу заявки:", reply_markup=builder.as_markup())
    await state.set_state(ApplicationStates.confirm)

# Кнопка "Назад" из выбора слота
@router.callback_query(ApplicationStates.select_timeslot, F.data == "app_back_city")
async def back_to_city(callback: CallbackQuery, state: FSMContext):
    await start_application(callback.message, state)

# Подтверждение заявки
@router.callback_query(ApplicationStates.confirm, F.data == "app_confirm")
async def confirm_application(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    city_id = data.get("city_id")
    timeslot_id = data.get("timeslot_id")
    user_id = callback.from_user.id
    try:
        # Создаём заявку (или возвращаем существующую)
        await get_or_create_application(user_id)
        builder = InlineKeyboardBuilder()
        builder.button(text="Статус заявки", callback_data="app_status")
        builder.button(text="Главное меню", callback_data="app_back_main")
        builder.adjust(1)
        await callback.message.edit_text("Ваша заявка отправлена! Статус: ожидание подтверждения.", reply_markup=builder.as_markup())
        await state.set_state(ApplicationStates.status)
    except Exception as e:
        logger.error(f"Ошибка при создании заявки: {e}")
        await callback.message.edit_text("Ошибка при создании заявки. Попробуйте позже.")

# Кнопка "Статус заявки" после подачи
@router.callback_query(F.data == "app_status")
async def show_application_status(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    application = await get_user_application(user_id)
    if application:
        text = (
            f"Ваша заявка:\nГород: {application['city_name']}\n"
            f"Время: {application['day_of_week']} {application['time'].strftime('%H:%M')}\n"
            f"Статус: {application['status']}"
        )
    else:
        text = "У вас нет активных заявок."
    builder = InlineKeyboardBuilder()
    builder.button(text="Главное меню", callback_data="app_back_main")
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await state.clear()

# Кнопка "Назад" из подтверждения
@router.callback_query(ApplicationStates.confirm, F.data == "app_back_slot")
async def back_to_slot(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    city_id = data.get("city_id")
    try:
        timeslots = await get_active_timeslots()
        filtered = [ts for ts in timeslots if ts["city_id"] == city_id]
        builder = InlineKeyboardBuilder()
        for slot in filtered:
            label = f"{slot['day_of_week']} {slot['start_time'].strftime('%H:%M')}"
            builder.button(text=label, callback_data=f"app_slot_{slot['id']}")
        builder.button(text="⬅️ Назад", callback_data="app_back_city")
        builder.adjust(1)
        await callback.message.edit_text("Выберите удобное время:", reply_markup=builder.as_markup())
        await state.set_state(ApplicationStates.select_timeslot)
    except Exception as e:
        logger.error(f"Ошибка при возврате к слотам: {e}")
        await callback.message.edit_text("Ошибка при возврате к выбору слотов. Попробуйте позже.")

# Просмотр своей заявки
@router.message(F.text == "📨 Мои заявки")
async def view_my_application(message: Message, state: FSMContext):
    user_id = message.from_user.id
    try:
        application = await get_user_application(user_id)
        if application:
            text = (
                f"Ваша заявка:\nГород: {application['city_name']}\n"
                f"Время: {application['day_of_week']} {application['time'].strftime('%H:%M')}\n"
                f"Статус: {application['status']}"
            )
            builder = InlineKeyboardBuilder()
            if application["status"] == "pending":
                builder.button(text="Отменить заявку", callback_data="app_cancel")
            builder.button(text="⬅️ Назад", callback_data="app_back_main")
            builder.adjust(1)
            await message.answer(text, reply_markup=builder.as_markup())
        else:
            await message.answer("У вас нет активных заявок.")
    except Exception as e:
        logger.error(f"Ошибка при просмотре заявки: {e}")
        await message.answer("Ошибка при получении вашей заявки. Попробуйте позже.")

# Отмена заявки
@router.callback_query(F.data == "app_cancel")
async def cancel_my_application(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    try:
        await cancel_application(user_id)
        builder = InlineKeyboardBuilder()
        builder.button(text="Главное меню", callback_data="app_back_main")
        builder.adjust(1)
        await callback.message.edit_text("Ваша заявка отменена.", reply_markup=builder.as_markup())
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка при отмене заявки: {e}")
        await callback.message.edit_text("Ошибка при отмене заявки. Попробуйте позже.") 