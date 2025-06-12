import pytest
import pytest_asyncio
from copy import deepcopy

class MockResponse:
    def __init__(self, text, keyboard=None, inline_keyboard=None):
        self.text = text
        # Поддержка и обычной, и inline клавиатуры
        if inline_keyboard is not None:
            self.keyboard = inline_keyboard
        else:
            self.keyboard = keyboard or []
    def get_inline_keyboard(self):
        return self.keyboard
    @property
    def reply_keyboard(self):
        return self.keyboard

class BotTester:
    def __init__(self):
        self.reset()

    def reset(self):
        # Состояние "мини-БД"
        self.profile = {'name': 'Иван', 'surname': 'Иванов', 'age': 30}
        self.application = None  # {'city': ..., 'slot': ..., 'status': ...}
        self.meetings = []  # [{'id': ..., 'city': ..., 'date': ..., 'time': ..., 'past': bool}]
        self.next_meeting_id = 1
        self.awaiting_cancel = None
        self.awaiting_meeting_cancel = None
        self.awaiting_feedback = None  # meeting_id, если ждём отзыв
        self.awaiting_rating = None
        self.awaiting_comment = None
        self.feedbacks = {}  # meeting_id: {'rating': int, 'comment': str}
        self.is_registered = True
        self.is_approved = True
        self.cities_available = True
        self.slots_available = True
        self.state_stack = []  # Для возвратов

    async def send_message(self, text):
        # Главное меню
        if text in ("/start", "Старт", "start"):
            return MockResponse("Добро пожаловать в 5 Chairs!", inline_keyboard=["📝 Подать заявку", "📅 Мои встречи", "👤 Профиль", "📨 Мои заявки", "❓ Помощь"])
        if text in ("Главное меню", "Назад", "В меню"):
            return MockResponse("Главное меню", inline_keyboard=["📝 Подать заявку", "📅 Мои встречи", "👤 Профиль", "📨 Мои заявки", "❓ Помощь"])
        if text == "📨 Мои заявки":
            return MockResponse("Ваши заявки и статусы (заглушка)", inline_keyboard=["⬅️ Назад"])
        if text == "❓ Помощь":
            return MockResponse("Раздел помощи (заглушка)", inline_keyboard=["В меню"])

        # FSM подачи заявки
        if text in ("Подать заявку", "📝 Подать заявку"):
            self.state_stack = ["MainMenu"]
            self.awaiting_city = True
            return MockResponse("Выберите город", inline_keyboard=["🏙️ Москва", "🏙️ Питер", "⬅️ Назад"])
        if hasattr(self, 'awaiting_city') and self.awaiting_city and text in ("🏙️ Москва", "🏙️ Питер"):
            self.state_stack.append("City")
            if not getattr(self, 'slots_available', True):
                self.awaiting_city = False
                return MockResponse("Нет доступных временных слотов для этого города.", inline_keyboard=["⬅️ Назад"])
            self.application = {'city': text, 'slot': None, 'status': 'select_slot'}
            self.awaiting_city = False
            self.awaiting_slot = True
            return MockResponse("Выберите удобное время", inline_keyboard=["18:00", "19:00", "⬅️ Назад"])
        if hasattr(self, 'awaiting_slot') and self.awaiting_slot and text in ("18:00", "19:00"):
            self.state_stack.append("TimeSlot")
            self.application['slot'] = text
            self.application['status'] = 'confirm'
            self.awaiting_slot = False
            self.awaiting_confirm = True
            return MockResponse("Подтвердите подачу заявки", inline_keyboard=["✅ Подтвердить", "⬅️ Назад"])
        if hasattr(self, 'awaiting_confirm') and self.awaiting_confirm and text == "✅ Подтвердить":
            self.state_stack.append("ConfirmApp")
            self.application['status'] = 'pending'
            self.awaiting_confirm = False
            return MockResponse("Ваша заявка отправлена, ожидание подтверждения", inline_keyboard=["В меню"])
        if text == "⬅️ Назад":
            if self.state_stack:
                last = self.state_stack.pop()
                if last == "TimeSlot":
                    self.awaiting_slot = False
                    self.awaiting_city = True
                    return MockResponse("Выберите город", inline_keyboard=["🏙️ Москва", "🏙️ Питер", "⬅️ Назад"])
                if last == "ConfirmApp":
                    self.awaiting_confirm = False
                    self.awaiting_slot = True
                    return MockResponse("Выберите удобное время", inline_keyboard=["18:00", "19:00", "⬅️ Назад"])
                if last == "City":
                    self.awaiting_city = False
                    return MockResponse("Главное меню", inline_keyboard=["📝 Подать заявку", "📅 Мои встречи", "👤 Профиль", "📨 Мои заявки", "❓ Помощь"])
            return MockResponse("Главное меню", inline_keyboard=["📝 Подать заявку", "📅 Мои встречи", "👤 Профиль", "📨 Мои заявки", "❓ Помощь"])
        if text == "В меню":
            return MockResponse("Главное меню", inline_keyboard=["📝 Подать заявку", "📅 Мои встречи", "👤 Профиль", "📨 Мои заявки", "❓ Помощь"])

        # Остальные разделы (заглушки)
        if text == "📅 Мои встречи":
            return MockResponse("Ближайшие/Прошедшие встречи (заглушка)", inline_keyboard=["📅 Ближайшие", "⏳ Прошедшие", "⬅️ Назад"])
        if text == "👤 Профиль":
            return MockResponse("Ваш профиль (заглушка)", inline_keyboard=["✏️ Редактировать анкету", "⬅️ Назад"])
        if text == "📅 Ближайшие":
            return MockResponse("Список ближайших встреч (заглушка)", inline_keyboard=["⬅️ Назад"])
        if text == "⏳ Прошедшие":
            return MockResponse("Список прошедших встреч (заглушка)", inline_keyboard=["⬅️ Назад"])
        if text == "✏️ Редактировать анкету":
            return MockResponse("Список вопросов (заглушка)", inline_keyboard=["Изменить ответ", "⬅️ Назад"])
        if text == "Изменить ответ":
            return MockResponse("Изменить ответ (заглушка)", inline_keyboard=["⬅️ Назад"])

        # Мои встречи
        if text == "Мои встречи":
            if not self.meetings:
                return MockResponse(
                    text='У вас пока нет встреч.',
                    inline_keyboard=['Главное меню']
                )
            keyboard = []
            lines = ['Ваши встречи:']
            for meeting in self.meetings:
                line = f"{meeting['date']} {meeting['time']} — {meeting['city']} (id={meeting['id']})"
                lines.append(line)
                if meeting.get('past') and meeting['id'] not in self.feedbacks:
                    keyboard.append(f'Оставить отзыв {meeting["id"]}')
                keyboard.append(f'Детали: {meeting["city"]}')
                keyboard.append(f'Отменить встречу {meeting["id"]}')
            keyboard.append('Главное меню')
            return MockResponse(
                text='\n'.join(lines),
                inline_keyboard=keyboard
            )
        if text.startswith("Отменить встречу"):
            try:
                meet_id = int(text.split()[-1])
                meeting = next(m for m in self.meetings if m['id'] == meet_id)
                self.awaiting_meeting_cancel = meet_id
                return MockResponse(
                    text=f"Вы уверены, что хотите отменить встречу {meeting['date']} {meeting['time']} в {meeting['city']}?",
                    inline_keyboard=['Да, отменить', 'Главное меню']
                )
            except Exception:
                return MockResponse(
                    text='Встреча не найдена',
                    inline_keyboard=['Главное меню']
                )
        if text == "Да, отменить" and self.awaiting_meeting_cancel:
            self.meetings = [m for m in self.meetings if m['id'] != self.awaiting_meeting_cancel]
            self.awaiting_meeting_cancel = None
            return MockResponse(
                text='Встреча отменена',
                inline_keyboard=['Главное меню']
            )
        if text.startswith('Детали:'):
            return MockResponse('Детали встречи: ...', inline_keyboard=['Главное меню'])

        # Оставить отзыв
        if text.startswith("Оставить отзыв"):
            try:
                meet_id = int(text.split()[-1])
                meeting = next(m for m in self.meetings if m['id'] == meet_id and m.get('past'))
                if meet_id in self.feedbacks:
                    return MockResponse("Вы уже оставили отзыв на эту встречу", ["Главное меню"])
                self.awaiting_feedback = meet_id
                self.awaiting_rating = True
                return MockResponse("Поставьте оценку встрече (1-5):", ["1", "2", "3", "4", "5", "Главное меню"])
            except Exception:
                return MockResponse("Встреча не найдена или не завершена", ["Главное меню"])
        if hasattr(self, 'awaiting_rating') and self.awaiting_rating and text in ("1", "2", "3", "4", "5"):
            self.feedbacks[self.awaiting_feedback] = {'rating': int(text), 'comment': None}
            self.awaiting_rating = False
            self.awaiting_comment = True
            return MockResponse("Оставьте комментарий к встрече:", ["Пропустить", "Главное меню"])
        if hasattr(self, 'awaiting_comment') and self.awaiting_comment:
            if text == "Пропустить":
                self.feedbacks[self.awaiting_feedback]['comment'] = ""
            else:
                self.feedbacks[self.awaiting_feedback]['comment'] = text
            self.awaiting_comment = False
            self.awaiting_feedback = None
            return MockResponse("Спасибо за ваш отзыв!", ["Главное меню"])

        # Специальные команды для тестов
        if text.startswith("_add_meeting "):
            parts = text.split()
            city, date, time = parts[1], parts[2], parts[3]
            past = False
            if len(parts) > 4 and parts[4] == 'past':
                past = True
            meeting = {
                'id': self.next_meeting_id,
                'city': city,
                'date': date,
                'time': time,
                'name': city,
                'past': past
            }
            self.meetings.append(meeting)
            self.next_meeting_id += 1
            return MockResponse("Встреча добавлена")
        if text == "_clear_meetings":
            self.meetings.clear()
            return MockResponse("Встречи очищены")
        if text == "_clear_applications":
            self.application = None
            return MockResponse("Заявки очищены")
        if text == "_reset":
            self.reset()
            return MockResponse("Состояние сброшено")

        # Ошибки и неизвестные команды
        if text == 'Ошибка' or text == 'Edge case':
            return MockResponse(
                text='Произошла ошибка.',
                inline_keyboard=['Главное меню']
            )
        return MockResponse(
            "Я не понял ваш запрос. Пожалуйста, воспользуйтесь меню или выберите действие на клавиатуре.",
            ["Главное меню"]
        )

    async def click_button(self, button_text):
        # FSM подачи заявки — обработка inline-кнопок
        if button_text in ("⬅️ Назад", "В меню"):
            return await self.send_message(button_text)
        if button_text in ("🏙️ Москва", "🏙️ Питер", "18:00", "19:00", "✅ Подтвердить"):
            return await self.send_message(button_text)
        # Главное меню и новые разделы
        if button_text in ("📝 Подать заявку", "📅 Мои встречи", "👤 Профиль", "📨 Мои заявки", "❓ Помощь"):
            return await self.send_message(button_text)
        # Остальные кнопки (заглушки)
        if button_text in ("📅 Ближайшие", "⏳ Прошедшие", "✏️ Редактировать анкету", "Изменить ответ"):
            return await self.send_message(button_text)
        # Кнопки встреч
        if button_text.startswith('Отменить встречу'):
            try:
                meet_id = int(button_text.split()[-1])
                meeting = next(m for m in self.meetings if m['id'] == meet_id)
                self.awaiting_meeting_cancel = meet_id
                return MockResponse(
                    text=f'Вы уверены, что хотите отменить встречу {meeting["date"]} {meeting["time"]} в {meeting["city"]}?',
                    inline_keyboard=['Да, отменить', 'Главное меню']
                )
            except Exception:
                return MockResponse('Встреча не найдена', inline_keyboard=['Главное меню'])
        if button_text == 'Да, отменить' and self.awaiting_meeting_cancel:
            self.meetings = [m for m in self.meetings if m['id'] != self.awaiting_meeting_cancel]
            self.awaiting_meeting_cancel = None
            return MockResponse('Встреча отменена', inline_keyboard=['Главное меню'])
        if button_text.startswith('Детали:'):
            return MockResponse('Детали встречи: ...', inline_keyboard=['Главное меню'])
        if button_text.startswith('Оставить отзыв'):
            try:
                meet_id = int(button_text.split()[-1])
                meeting = next(m for m in self.meetings if m['id'] == meet_id and m.get('past'))
                if meet_id in self.feedbacks:
                    return MockResponse("Вы уже оставили отзыв на эту встречу", ["Главное меню"])
                self.awaiting_feedback = meet_id
                self.awaiting_rating = True
                return MockResponse("Поставьте оценку встрече (1-5):", ["1", "2", "3", "4", "5", "Главное меню"])
            except Exception:
                return MockResponse("Встреча не найдена или не завершена", ["Главное меню"])
        if button_text in ("1", "2", "3", "4", "5") and hasattr(self, 'awaiting_rating') and self.awaiting_rating:
            self.feedbacks[self.awaiting_feedback] = {'rating': int(button_text), 'comment': None}
            self.awaiting_rating = False
            self.awaiting_comment = True
            return MockResponse("Оставьте комментарий к встрече:", ["Пропустить", "Главное меню"])
        if button_text == "Пропустить" and hasattr(self, 'awaiting_comment') and self.awaiting_comment:
            self.feedbacks[self.awaiting_feedback]['comment'] = ""
            self.awaiting_comment = False
            self.awaiting_feedback = None
            return MockResponse("Спасибо за ваш отзыв!", ["Главное меню"])
        if button_text == 'Главное меню':
            return MockResponse('Главное меню', inline_keyboard=['Мои встречи', 'Профиль', 'Подать заявку', 'Главное меню'])
        # Для других кнопок — универсальный возврат
        return MockResponse('Я не понял ваш запрос. Пожалуйста, воспользуйтесь меню или выберите действие на клавиатуре.', inline_keyboard=['Главное меню'])

@pytest_asyncio.fixture
async def bot_tester():
    tester = BotTester()
    tester.reset()
    return tester 