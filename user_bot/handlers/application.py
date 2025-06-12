import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.db import get_active_cities, get_active_timeslots, get_or_create_application, get_user_application, pool, get_user
from user_bot.handlers.start import get_main_menu
from aiogram.filters import Command

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
async def start_application(message: Message, state: FSMContext, is_callback: bool = False):
    user_id = message.from_user.id
    user = await get_user(user_id)
    logger.info(f"start_application: user_id={user_id}")
    logger.info(f"start_application: get_user({user_id}) -> {user}")
    if not user:
        msg = await message.answer("Вы не зарегистрированы. Пожалуйста, пройдите регистрацию через /start.")
        await state.update_data(last_private_message_id=msg.message_id)
        return
    logger.info(f"start_application: user['status'] = {user.get('status')}")
    if user["status"] == "rejected":
        msg = await message.answer("Ваша регистрация отклонена. Обратитесь к администратору.")
        await state.update_data(last_private_message_id=msg.message_id)
        return
    try:
        cities = await get_active_cities()
        if not cities:
            builder = InlineKeyboardBuilder()
            builder.button(text="В меню", callback_data="main_menu")
            builder.adjust(1)
            if is_callback:
                msg = await message.message.edit_text("Нет доступных городов для подачи заявки.", reply_markup=builder.as_markup())
            else:
                msg = await message.answer("Нет доступных городов для подачи заявки.", reply_markup=builder.as_markup())
            await state.update_data(last_private_message_id=msg.message_id)
            return
        builder = InlineKeyboardBuilder()
        for city in cities:
            builder.button(text=city["name"], callback_data=f"app_city_{city['id']}")
        builder.button(text="В меню", callback_data="main_menu")
        builder.adjust(1)
        if is_callback:
            msg = await message.message.edit_text("Выберите город:", reply_markup=builder.as_markup())
        else:
            msg = await message.answer("Выберите город:", reply_markup=builder.as_markup())
        await state.update_data(last_private_message_id=msg.message_id)
        await state.set_state(ApplicationStates.select_city)
    except Exception as e:
        logger.error(f"Ошибка при получении городов: {e}")
        if is_callback:
            msg = await message.message.edit_text("Ошибка при получении списка городов. Попробуйте позже.")
        else:
            msg = await message.answer("Ошибка при получении списка городов. Попробуйте позже.")
        await state.update_data(last_private_message_id=msg.message_id)

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
            builder.button(text="В меню", callback_data="main_menu")
            builder.adjust(1)
            await callback.message.edit_text("Нет доступных временных слотов для этого города.", reply_markup=builder.as_markup())
            return
        builder = InlineKeyboardBuilder()
        for slot in filtered:
            label = f"{slot['day_of_week']} {slot['start_time'].strftime('%H:%M')}"
            builder.button(text=label, callback_data=f"app_slot_{slot['id']}")
        builder.button(text="В меню", callback_data="main_menu")
        builder.adjust(1)
        await callback.message.edit_text("Выберите удобное время:", reply_markup=builder.as_markup())
        await state.set_state(ApplicationStates.select_timeslot)
    except Exception as e:
        logger.error(f"Ошибка при получении слотов: {e}")
        await callback.message.edit_text("Ошибка при получении временных слотов. Попробуйте позже.")

# Выбор временного слота
@router.callback_query(ApplicationStates.select_timeslot, F.data.startswith("app_slot_"))
async def select_timeslot(callback: CallbackQuery, state: FSMContext):
    slot_id = int(callback.data.split("_")[-1])
    await state.update_data(timeslot_id=slot_id)
    builder = InlineKeyboardBuilder()
    builder.button(text="Подтвердить заявку", callback_data="app_confirm")
    builder.button(text="⬅️ Назад", callback_data="app_back_slot")
    builder.adjust(1)
    msg = await callback.message.edit_text("Подтвердите подачу заявки:", reply_markup=builder.as_markup())
    await state.update_data(last_private_message_id=msg.message_id)
    await state.set_state(ApplicationStates.confirm)

# Подтверждение заявки
@router.callback_query(ApplicationStates.confirm, F.data == "app_confirm")
async def confirm_application(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    city_id = data.get("city_id")
    timeslot_id = data.get("timeslot_id")
    user_id = callback.from_user.id
    try:
        # Создаём заявку (или возвращаем существующую) для этого слота
        await get_or_create_application(user_id, timeslot_id)
        # Получаем название города и параметры слота
        async with pool.acquire() as conn:
            city = await conn.fetchrow('SELECT name FROM cities WHERE id = $1', city_id)
            slot = await conn.fetchrow('SELECT day_of_week, start_time FROM time_slots WHERE id = $1', timeslot_id)
        city_name = city['name'] if city else '-'
        day_of_week = slot['day_of_week'] if slot else '-'
        time_str = slot['start_time'].strftime('%H:%M') if slot and slot['start_time'] else '-'
        text = (
            "Ваша заявка отправлена!\n\n"
            f"Город: {city_name}\n"
            f"Время: {day_of_week} {time_str}\n"
            "Статус: ожидание подтверждения."
        )
        builder = InlineKeyboardBuilder()
        builder.button(text="В меню", callback_data="main_menu")
        builder.adjust(1)
        msg = await callback.message.edit_text(text, reply_markup=builder.as_markup())
        await state.update_data(last_private_message_id=msg.message_id)
        await state.set_state(ApplicationStates.status)
    except Exception as e:
        logger.error(f"Ошибка при создании заявки: {e}")
        await callback.message.edit_text("Ошибка при создании заявки. Попробуйте позже.")

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
            builder.button(text="В меню", callback_data="main_menu")
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
        builder.button(text="В меню", callback_data="main_menu")
        builder.adjust(1)
        msg = await callback.message.edit_text("Ваша заявка отменена.", reply_markup=builder.as_markup())
        await state.update_data(last_private_message_id=msg.message_id)
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка при отмене заявки: {e}")
        await callback.message.edit_text("Ошибка при отмене заявки. Попробуйте позже.") 

# Универсальный обработчик возврата в главное меню из любого места
@router.callback_query(F.data == "main_menu")
async def cb_main_menu_application(callback: CallbackQuery, state: FSMContext):
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
        "Главное меню. Выберите действие:",
        reply_markup=get_main_menu()
    )
    await state.clear()

@router.message(Command("apply"))
async def cmd_apply(message: Message, state: FSMContext):
    # ... логика выбора города и слота ...
    msg = await message.answer("Выберите город для встречи:", reply_markup=builder.as_markup())
    await state.update_data(last_private_message_id=msg.message_id)

@router.callback_query(F.data.startswith("confirm_application_"))
async def confirm_application(callback: CallbackQuery, state: FSMContext):
    # ... логика подтверждения заявки ...
    msg = await callback.message.edit_text("Ваша заявка подтверждена!", reply_markup=builder.as_markup())
    await state.update_data(last_private_message_id=msg.message_id)

@router.callback_query(F.data == "cancel_application")
async def cancel_application(callback: CallbackQuery, state: FSMContext):
    # ... логика отмены заявки ...
    msg = await callback.message.edit_text("Заявка отменена.", reply_markup=builder.as_markup())
    await state.update_data(last_private_message_id=msg.message_id)

@router.message(Command("application_status"))
async def show_application_status(message: Message, state: FSMContext):
    # ... логика показа статуса заявки ...
    msg = await message.answer("Статус вашей заявки: ...", reply_markup=builder.as_markup())
    await state.update_data(last_private_message_id=msg.message_id)

# Восстанавливаю обработчик для 'app_back_slot'
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
        builder.button(text="В меню", callback_data="main_menu")
        builder.adjust(1)
        msg = await callback.message.edit_text("Выберите удобное время:", reply_markup=builder.as_markup())
        await state.update_data(last_private_message_id=msg.message_id)
        await state.set_state(ApplicationStates.select_timeslot)
    except Exception as e:
        logger.error(f"Ошибка при возврате к слотам: {e}")
        await callback.message.edit_text("Ошибка при возврате к выбору слотов. Попробуйте позже.") 