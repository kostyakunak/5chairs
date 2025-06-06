# MVP ROADMAP & QUICK FIXES

## Цель

Быстро довести сервис до минимально жизнеспособного состояния (MVP):
- Сервис должен запускаться без ошибок
- Основные сценарии user/admin flow должны работать
- Все советы — только для ускорения запуска и устранения блокеров

---

## 1. Проверка запуска

- Убедиться, что все зависимости установлены:
  ```bash
  pip install -r requirements.txt
  ```
- Проверить .env (минимум: DATABASE_URL, токены ботов)
- Применить миграции:
  ```bash
  alembic upgrade head
  ```
- Запустить сервисы:
  ```bash
  python run_user_bot.py
  python run_admin_bot.py
  python run_notification_service.py
  # (если есть) python run_timeslot_service.py
  ```
- Проверить логи на наличие ошибок запуска

---

## 2. Ручное тестирование основных сценариев

- Пользователь:
  - Может выбрать город, подать заявку, пройти анкету
- Админ:
  - Видит заявки, может одобрить/отклонить, распределить пользователя
- Проверить, что уведомления доходят

---

## 3. Лог багов и решений (заполнять по ходу)

| Дата       | Описание бага/ошибки         | Решение/фикс                |
|------------|------------------------------|-----------------------------|
| 2024-06-XX | Пример: не запускается бот   | Добавил переменную в .env   |
|            |                              |                             |

---

## 4. Мини-документация для ИИ-ассистента

- **Точки входа:**
  - run_user_bot.py, run_admin_bot.py, run_notification_service.py, run_timeslot_service.py (опционально)
- **Структура БД:**
  - users, admins, applications, meetings, time_slots, cities, venues, meeting_members, meeting_time_slots, available_dates, questions, user_answers
- **Пример .env:**
  ```env
  DATABASE_URL=postgresql://user:pass@localhost:5432/dbname
  USER_BOT_TOKEN=xxx
  ADMIN_BOT_TOKEN=xxx
  # ... другие нужные переменные
  ```
- **Пример команды миграции:**
  ```bash
  alembic upgrade head
  ```
- **Пример запуска:**
  ```bash
  python run_user_bot.py
  ```

---

## 5. Советы

- Не заниматься рефакторингом и улучшениями, пока не работает MVP!
- Все найденные баги и решения фиксировать в лог выше
- Если что-то не работает — сначала проверить .env, миграции, импорты
- Минимум документации — только то, что реально помогает запуску и отладке

---

**Этот файл держать рядом с Detailed_Service_Work.md и обновлять только по мере появления новых багов/решений или изменений в запуске.** 