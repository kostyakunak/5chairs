import pytest
import pytest_asyncio  # Для корректной работы @pytest.mark.asyncio
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

# Здесь предполагается использование aiogram test utilities или аналогичного подхода
# Ниже — структура и заглушки для основных пользовательских сценариев

# Используется мок-бот через фикстуру bot_tester из conftest.py

@pytest.mark.asyncio
async def test_start_command(bot_tester):
    """Пользователь запускает бота и получает приветствие."""
    response = await bot_tester.send_message('/start')
    assert 'Добро пожаловать' in response.text

@pytest.mark.asyncio
async def test_apply_flow(bot_tester):
    """Подача заявки: выбор города, дня, слота, подтверждение."""
    response = await bot_tester.send_message('📝 Подать заявку')
    assert 'Выберите город' in response.text

    city_button = response.get_inline_keyboard()[0]
    response = await bot_tester.click_button(city_button)
    assert 'Выберите удобное время' in response.text

    slot_button = response.get_inline_keyboard()[0]
    response = await bot_tester.click_button(slot_button)
    assert 'Подтвердите подачу заявки' in response.text

    confirm_button = response.get_inline_keyboard()[0]
    response = await bot_tester.click_button(confirm_button)
    assert 'Ваша заявка отправлена' in response.text
    assert 'ожидание подтверждения' in response.text

@pytest.mark.asyncio
async def test_repeat_application(bot_tester):
    # Подаём заявку
    await bot_tester.send_message('Подать заявку')
    await bot_tester.send_message('Москва')
    await bot_tester.send_message('18:00')
    await bot_tester.send_message('Подтвердить')
    # Пытаемся подать ещё раз
    response = await bot_tester.send_message('Подать заявку')
    assert 'уже есть активная заявка' in response.text.lower()
    # Отменяем заявку
    response = await bot_tester.send_message('Отменить заявку')
    assert 'Заявка отменена' in response.text
    # Теперь можно подать снова
    response = await bot_tester.send_message('Подать заявку')
    assert 'Выберите город' in response.text

@pytest.mark.asyncio
async def test_cancel_application(bot_tester):
    await bot_tester.send_message('Подать заявку')
    await bot_tester.send_message('Москва')
    await bot_tester.send_message('18:00')
    await bot_tester.send_message('Подтвердить')
    response = await bot_tester.send_message('Отменить заявку')
    assert 'Заявка отменена' in response.text
    response = await bot_tester.send_message('Статус заявки')
    assert 'нет активных заявок' in response.text.lower()

@pytest.mark.asyncio
async def test_meetings_add_and_cancel(bot_tester):
    # Добавляем встречи через спецкоманду
    await bot_tester.send_message('_add_meeting Москва 2024-06-10 18:00')
    await bot_tester.send_message('_add_meeting Питер 2024-06-15 19:00')
    response = await bot_tester.send_message('Мои встречи')
    assert 'Москва' in response.text and 'Питер' in response.text
    # Отменяем первую встречу
    cancel_btn = response.get_inline_keyboard()[0]
    response = await bot_tester.click_button(cancel_btn)
    assert 'Вы уверены' in response.text
    response = await bot_tester.click_button('Да, отменить')
    assert 'Встреча отменена' in response.text
    response = await bot_tester.send_message('Мои встречи')
    assert 'Москва' not in response.text
    # Очищаем встречи
    response = await bot_tester.send_message('_clear_meetings')
    assert 'очищены' in response.text
    response = await bot_tester.send_message('Мои встречи')
    assert 'нет встреч' in response.text.lower()

@pytest.mark.asyncio
async def test_profile_edit(bot_tester):
    response = await bot_tester.send_message('Профиль')
    assert 'Ваш профиль' in response.text
    response = await bot_tester.click_button('Редактировать')
    assert 'Введите новое имя' in response.text
    response = await bot_tester.send_message('Пётр')
    assert 'Введите новую фамилию' in response.text
    response = await bot_tester.send_message('Петров')
    assert 'Введите новый возраст' in response.text
    response = await bot_tester.send_message('35')
    assert 'Профиль обновлён' in response.text
    response = await bot_tester.send_message('Профиль')
    assert 'Пётр' in response.text and 'Петров' in response.text and '35' in response.text

@pytest.mark.asyncio
async def test_reset_state(bot_tester):
    await bot_tester.send_message('Подать заявку')
    await bot_tester.send_message('Москва')
    await bot_tester.send_message('18:00')
    await bot_tester.send_message('Подтвердить')
    await bot_tester.send_message('_add_meeting Москва 2024-06-10 18:00')
    response = await bot_tester.send_message('_reset')
    assert 'сброшено' in response.text.lower()
    response = await bot_tester.send_message('Статус заявки')
    assert 'нет активных заявок' in response.text.lower()
    response = await bot_tester.send_message('Мои встречи')
    assert 'нет встреч' in response.text.lower()

@pytest.mark.asyncio
async def test_meetings_list(bot_tester):
    await bot_tester.send_message('_add_meeting Москва 2024-06-10 18:00')
    response = await bot_tester.send_message('Мои встречи')
    assert 'Ваши встречи' in response.text
    keyboard = response.get_inline_keyboard()
    assert any('Отменить встречу' in btn for btn in keyboard)
    assert 'Назад' in keyboard

@pytest.mark.asyncio
async def test_meetings_empty(bot_tester):
    await bot_tester.send_message('_clear_meetings')
    response = await bot_tester.send_message('Мои встречи')
    assert 'нет встреч' in response.text.lower()
    assert 'Назад' in response.get_inline_keyboard()

@pytest.mark.asyncio
async def test_no_cities(bot_tester):
    """Нет доступных городов — бот сообщает об этом корректно и предлагает вернуться в меню."""
    bot_tester.cities_available = False
    response = await bot_tester.send_message('📝 Подать заявку')
    assert 'нет доступных городов' in response.text.lower()
    assert any('меню' in btn.lower() for btn in response.get_inline_keyboard())
    # Клик по кнопке "В меню" возвращает в главное меню
    menu_btn = next(btn for btn in response.get_inline_keyboard() if 'меню' in btn.lower())
    response = await bot_tester.click_button(menu_btn)
    assert 'главное меню' in response.text.lower()

@pytest.mark.asyncio
async def test_no_slots(bot_tester):
    """Нет доступных слотов для города — бот сообщает об этом корректно и предлагает вернуться в меню."""
    bot_tester.cities_available = True
    bot_tester.slots_available = False
    response = await bot_tester.send_message('📝 Подать заявку')
    city_btn = response.get_inline_keyboard()[0]
    response = await bot_tester.click_button(city_btn)
    assert 'нет доступных временных слотов' in response.text.lower()
    assert any('меню' in btn.lower() for btn in response.get_inline_keyboard())
    menu_btn = next(btn for btn in response.get_inline_keyboard() if 'меню' in btn.lower())
    response = await bot_tester.click_button(menu_btn)
    assert 'главное меню' in response.text.lower()

@pytest.mark.asyncio
async def test_status_check(bot_tester):
    await bot_tester.send_message('Подать заявку')
    await bot_tester.send_message('Москва')
    await bot_tester.send_message('18:00')
    await bot_tester.send_message('Подтвердить')
    response = await bot_tester.send_message('Статус заявки')
    assert 'pending' in response.text or 'ожидание' in response.text.lower()

@pytest.mark.asyncio
async def test_receive_notification(bot_tester):
    """Пользователь получает уведомление об одобрении/отклонении заявки."""
    response = await bot_tester.send_message('simulate_admin_action:approve')
    assert response.text

@pytest.mark.asyncio
async def test_feedback_flow(bot_tester):
    await bot_tester.send_message('_add_meeting Москва 2024-06-01 18:00 past')
    response = await bot_tester.send_message('Мои встречи')
    feedback_btn = next(btn for btn in response.get_inline_keyboard() if 'Оставить отзыв' in btn)
    response = await bot_tester.click_button(feedback_btn)
    assert 'оценку' in response.text
    response = await bot_tester.click_button('5')
    assert 'комментарий' in response.text
    response = await bot_tester.send_message('Отличная встреча!')
    assert 'Спасибо за ваш отзыв' in response.text
    response = await bot_tester.send_message('Мои встречи')
    feedback_btns = [btn for btn in response.get_inline_keyboard() if 'Оставить отзыв' in btn]
    assert not feedback_btns
    response = await bot_tester.send_message('Оставить отзыв 1')
    assert 'уже оставили' in response.text

@pytest.mark.asyncio
async def test_feedback_skip_comment(bot_tester):
    await bot_tester.send_message('_add_meeting Питер 2024-06-02 19:00 past')
    response = await bot_tester.send_message('Мои встречи')
    feedback_btn = next(btn for btn in response.get_inline_keyboard() if 'Оставить отзыв' in btn)
    response = await bot_tester.click_button(feedback_btn)
    response = await bot_tester.click_button('4')
    response = await bot_tester.click_button('Пропустить')
    assert 'Спасибо за ваш отзыв' in response.text

@pytest.mark.asyncio
async def test_feedback_only_for_past(bot_tester):
    await bot_tester.send_message('_add_meeting Казань 2024-07-01 18:00')
    response = await bot_tester.send_message('Мои встречи')
    assert not any('Оставить отзыв' in btn for btn in response.get_inline_keyboard())
    response = await bot_tester.send_message('Оставить отзыв 2')
    assert 'не найдена' in response.text or 'не завершена' in response.text

@pytest.mark.asyncio
async def test_unknown_command(bot_tester):
    response = await bot_tester.send_message('abrakadabra')
    assert 'не понял' in response.text.lower()
    assert 'Главное меню' in response.get_inline_keyboard()

@pytest.mark.asyncio
async def test_invalid_feedback(bot_tester):
    # Попытка оставить отзыв на несуществующую встречу
    response = await bot_tester.send_message('Оставить отзыв 999')
    assert 'не найдена' in response.text or 'не завершена' in response.text or 'не понял' in response.text
    assert 'Главное меню' in response.get_inline_keyboard() or 'Мои встречи' in response.get_inline_keyboard()

@pytest.mark.asyncio
async def test_menu_always_available(bot_tester):
    # В любой момент можно вернуться в главное меню
    await bot_tester.send_message('abrakadabra')
    response = await bot_tester.send_message('Главное меню')
    assert 'Главное меню' in response.text
    assert 'Главное меню' in response.get_inline_keyboard()

@pytest.mark.asyncio
async def test_apply_unregistered_user(bot_tester):
    """Незарегистрированный пользователь не может подать заявку."""
    bot_tester.is_registered = False
    response = await bot_tester.send_message('📝 Подать заявку')
    assert 'не зарегистрированы' in response.text.lower()

@pytest.mark.asyncio
async def test_apply_not_approved_user(bot_tester):
    """Пользователь с не-"approved" статусом не может подать заявку."""
    bot_tester.is_registered = True
    bot_tester.is_approved = False
    response = await bot_tester.send_message('📝 Подать заявку')
    assert 'не одобрена' in response.text.lower() or 'ожидайте подтверждения' in response.text.lower()

# Дополнительные тесты для обработки ошибок, возврата в меню и т.д. можно добавить по мере необходимости. 