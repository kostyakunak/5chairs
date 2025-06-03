import pytest
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

# Здесь предполагается использование aiogram test utilities или аналогичного подхода
# Ниже — структура и заглушки для основных пользовательских сценариев

@pytest.mark.asyncio
async def test_start_command(bot_tester):
    """Пользователь запускает бота и получает приветствие."""
    # await bot_tester.send_message('/start')
    # assert ... (проверка приветствия)
    pass

@pytest.mark.asyncio
async def test_apply_flow(bot_tester):
    """Подача заявки: выбор города, дня, слота, ответы на вопросы, подтверждение."""
    # await bot_tester.send_message('Подать заявку')
    # await bot_tester.click_button('Город N')
    # ...
    # assert ... (проверка финального сообщения)
    pass

@pytest.mark.asyncio
async def test_no_cities(bot_tester):
    """Нет доступных городов — бот сообщает об этом корректно."""
    # await bot_tester.send_message('Подать заявку')
    # assert ... (сообщение об отсутствии городов)
    pass

@pytest.mark.asyncio
async def test_repeat_application(bot_tester):
    """Пользователь пытается подать заявку повторно — бот корректно реагирует."""
    # await bot_tester.send_message('Подать заявку')
    # ...
    # await bot_tester.send_message('Подать заявку')
    # assert ... (сообщение о невозможности повторной подачи)
    pass

@pytest.mark.asyncio
async def test_cancel_application(bot_tester):
    """Пользователь отменяет заявку на любом этапе — бот возвращает в меню."""
    # await bot_tester.send_message('Подать заявку')
    # await bot_tester.click_button('Главное меню')
    # assert ... (возврат в главное меню)
    pass

@pytest.mark.asyncio
async def test_status_check(bot_tester):
    """Пользователь проверяет статус своей заявки."""
    # await bot_tester.send_message('Статус заявки')
    # assert ... (статус отображается корректно)
    pass

@pytest.mark.asyncio
async def test_receive_notification(bot_tester):
    """Пользователь получает уведомление об одобрении/отклонении заявки."""
    # await bot_tester.simulate_admin_action('approve')
    # assert ... (уведомление получено)
    pass

# Дополнительные тесты для обработки ошибок, возврата в меню и т.д. можно добавить по мере необходимости. 