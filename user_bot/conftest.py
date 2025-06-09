import pytest
import pytest_asyncio
from copy import deepcopy

class MockResponse:
    def __init__(self, text, keyboard=None):
        self.text = text
        self._keyboard = keyboard or []
    def get_inline_keyboard(self):
        return self._keyboard

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

    async def send_message(self, text):
        # Главное меню
        if text in ("/start", "Старт", "start"):
            return MockResponse("Добро пожаловать в 5 Chairs!", ["Мои встречи", "Профиль", "Подать заявку", "Главное меню"])
        if text in ("Главное меню", "Назад"):
            return MockResponse("Главное меню", ["Мои встречи", "Профиль", "Подать заявку", "Главное меню"])

        # Подача заявки
        if text in ("Подать заявку", "📝 Подать заявку"):
            if not getattr(self, 'is_registered', True):
                return MockResponse("Вы не зарегистрированы. Пожалуйста, пройдите регистрацию через /start.")
            if not getattr(self, 'is_approved', True):
                return MockResponse("Ваша регистрация ещё не одобрена администратором. Ожидайте подтверждения.")
            if not getattr(self, 'cities_available', True):
                return MockResponse("Нет доступных городов для подачи заявки.", ["В меню"])
            if self.application and self.application['status'] == 'pending':
                return MockResponse("У вас уже есть активная заявка", ["Статус заявки", "Отменить заявку", "Главное меню"])
            self.awaiting_city = True
            return MockResponse("Выберите город", ["Москва", "Питер"])
        if hasattr(self, 'awaiting_city') and self.awaiting_city and text in ("Москва", "Питер"):
            if not getattr(self, 'slots_available', True):
                self.awaiting_city = False
                return MockResponse("Нет доступных временных слотов для этого города.", ["В меню"])
            self.application = {'city': text, 'slot': None, 'status': 'select_slot'}
            self.awaiting_city = False
            self.awaiting_slot = True
            return MockResponse("Выберите удобное время", ["18:00", "19:00"])
        if hasattr(self, 'awaiting_slot') and self.awaiting_slot and text in ("18:00", "19:00"):
            self.application['slot'] = text
            self.application['status'] = 'confirm'
            self.awaiting_slot = False
            self.awaiting_confirm = True
            return MockResponse("Подтвердите подачу заявки", ["Подтвердить", "Главное меню"])
        if hasattr(self, 'awaiting_confirm') and self.awaiting_confirm and text == "Подтвердить":
            self.application['status'] = 'pending'
            self.awaiting_confirm = False
            return MockResponse("Ваша заявка отправлена, ожидание подтверждения", ["Статус заявки", "Главное меню"])
        if text == "Отменить заявку" and self.application and self.application['status'] == 'pending':
            self.application = None
            return MockResponse("Заявка отменена", ["Главное меню"])
        if text == "Статус заявки":
            if self.application:
                return MockResponse(f"Статус вашей заявки: {self.application['status']}", ["Главное меню"])
            else:
                return MockResponse("У вас нет активных заявок", ["Главное меню"])

        # Мои встречи
        if text in ("Мои встречи", "Мои встречи 📅"):
            if not self.meetings:
                return MockResponse("У вас пока нет встреч", ["Назад"])
            keyboard = []
            text_lines = ["Ваши встречи:"]
            for m in self.meetings:
                line = f"{m['date']} {m['time']} — {m['city']} (id={m['id']})"
                if m.get('past'):
                    if m['id'] in self.feedbacks:
                        line += " (отзыв оставлен)"
                    else:
                        keyboard.append(f"Оставить отзыв {m['id']}")
                else:
                    keyboard.append(f"Отменить встречу {m['id']}")
                text_lines.append(line)
            keyboard.append("Назад")
            return MockResponse("\n".join(text_lines), keyboard)
        if text.startswith("Отменить встречу"):
            try:
                meet_id = int(text.split()[-1])
                meeting = next(m for m in self.meetings if m['id'] == meet_id)
                self.awaiting_meeting_cancel = meet_id
                return MockResponse(f"Вы уверены, что хотите отменить встречу {meeting['date']} {meeting['time']} в {meeting['city']}?", ["Да, отменить", "Нет"])
            except Exception:
                return MockResponse("Встреча не найдена", ["Назад"])
        if text == "Да, отменить" and self.awaiting_meeting_cancel:
            self.meetings = [m for m in self.meetings if m['id'] != self.awaiting_meeting_cancel]
            self.awaiting_meeting_cancel = None
            return MockResponse("Встреча отменена", ["Мои встречи", "Главное меню"])
        if text == "Нет":
            self.awaiting_meeting_cancel = None
            return MockResponse("Отмена действия", ["Мои встречи", "Главное меню"])

        # Оставить отзыв
        if text.startswith("Оставить отзыв"):
            try:
                meet_id = int(text.split()[-1])
                meeting = next(m for m in self.meetings if m['id'] == meet_id and m.get('past'))
                if meet_id in self.feedbacks:
                    return MockResponse("Вы уже оставили отзыв на эту встречу", ["Мои встречи"])
                self.awaiting_feedback = meet_id
                self.awaiting_rating = True
                return MockResponse("Поставьте оценку встрече (1-5):", ["1", "2", "3", "4", "5"])
            except Exception:
                return MockResponse("Встреча не найдена или не завершена", ["Мои встречи"])
        if hasattr(self, 'awaiting_rating') and self.awaiting_rating and text in ("1", "2", "3", "4", "5"):
            self.feedbacks[self.awaiting_feedback] = {'rating': int(text), 'comment': None}
            self.awaiting_rating = False
            self.awaiting_comment = True
            return MockResponse("Оставьте комментарий к встрече:", ["Пропустить"])
        if hasattr(self, 'awaiting_comment') and self.awaiting_comment:
            if text == "Пропустить":
                self.feedbacks[self.awaiting_feedback]['comment'] = ""
            else:
                self.feedbacks[self.awaiting_feedback]['comment'] = text
            self.awaiting_comment = False
            self.awaiting_feedback = None
            return MockResponse("Спасибо за ваш отзыв!", ["Мои встречи", "Главное меню"])

        # Профиль
        if text == "Профиль":
            profile = self.profile
            return MockResponse(f"Ваш профиль:\nИмя: {profile['name']}\nФамилия: {profile['surname']}\nВозраст: {profile['age']}", ["Редактировать", "Главное меню"])
        if text == "Редактировать":
            self.awaiting_edit = 'name'
            return MockResponse("Введите новое имя:", ["Главное меню"])
        if hasattr(self, 'awaiting_edit') and self.awaiting_edit == 'name':
            self.profile['name'] = text
            self.awaiting_edit = 'surname'
            return MockResponse("Введите новую фамилию:", ["Главное меню"])
        if hasattr(self, 'awaiting_edit') and self.awaiting_edit == 'surname':
            self.profile['surname'] = text
            self.awaiting_edit = 'age'
            return MockResponse("Введите новый возраст:", ["Главное меню"])
        if hasattr(self, 'awaiting_edit') and self.awaiting_edit == 'age':
            try:
                self.profile['age'] = int(text)
            except Exception:
                pass
            self.awaiting_edit = None
            return MockResponse("Профиль обновлён", ["Профиль", "Главное меню"])

        # Специальные команды для тестов
        if text.startswith("_add_meeting "):
            # _add_meeting Москва 2024-06-10 18:00 [past]
            parts = text.split()
            city, date, time = parts[1], parts[2], parts[3]
            past = False
            if len(parts) > 4 and parts[4] == 'past':
                past = True
            self.meetings.append({'id': self.next_meeting_id, 'city': city, 'date': date, 'time': time, 'past': past})
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

        return MockResponse(
            "Я не понял ваш запрос. Пожалуйста, воспользуйтесь меню или выберите действие на клавиатуре.",
            ["Главное меню"]
        )

    async def click_button(self, button):
        # Обработка кнопки "В меню"
        if button == "В меню":
            return MockResponse("Главное меню. Выберите действие.", ["Мои встречи", "Профиль", "Подать заявку", "Главное меню"])
        return await self.send_message(button)

@pytest_asyncio.fixture
async def bot_tester():
    tester = BotTester()
    tester.reset()
    return tester 