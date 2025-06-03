-- SQL скрипт для сброса и заполнения тестовыми данными базы five_chairs
-- Автор: Claude
-- Дата: 09.05.2025

-- Начинаем транзакцию
BEGIN;

-- 1. Очистка базы данных (удаление всех существующих данных)
-- Отключаем проверку внешних ключей на время очистки
SET CONSTRAINTS ALL DEFERRED;

-- Очищаем таблицы с данными пользователей и заявок
TRUNCATE TABLE meeting_members CASCADE;
TRUNCATE TABLE group_members CASCADE;
TRUNCATE TABLE event_applications CASCADE;
TRUNCATE TABLE user_answers CASCADE;
TRUNCATE TABLE applications CASCADE;
TRUNCATE TABLE users CASCADE;
TRUNCATE TABLE events CASCADE;

-- Восстанавливаем проверку внешних ключей
SET CONSTRAINTS ALL IMMEDIATE;

-- 2. Сбрасываем счетчики последовательностей
ALTER SEQUENCE users_id_seq RESTART WITH 1;
ALTER SEQUENCE applications_id_seq RESTART WITH 1;
ALTER SEQUENCE event_applications_id_seq RESTART WITH 1;
ALTER SEQUENCE user_answers_id_seq RESTART WITH 1;
ALTER SEQUENCE events_id_seq RESTART WITH 1;

-- 3. Создаем 5 тестовых пользователей
INSERT INTO users (username, name, surname, age, registration_date, status)
VALUES 
    ('user1', 'Александр', 'Иванов', 28, CURRENT_DATE - INTERVAL '7 days', 'approved'),
    ('user2', 'Екатерина', 'Смирнова', 32, CURRENT_DATE - INTERVAL '6 days', 'approved'),
    ('user3', 'Михаил', 'Козлов', 25, CURRENT_DATE - INTERVAL '5 days', 'pending'),
    ('user4', 'Ольга', 'Новикова', 30, CURRENT_DATE - INTERVAL '4 days', 'pending'),
    ('user5', 'Дмитрий', 'Соколов', 35, CURRENT_DATE - INTERVAL '3 days', 'pending');

-- 4. Создаем заявки для каждого пользователя
INSERT INTO applications (user_id, created_at)
VALUES 
    (1, CURRENT_TIMESTAMP - INTERVAL '6 days'),
    (2, CURRENT_TIMESTAMP - INTERVAL '5 days'),
    (3, CURRENT_TIMESTAMP - INTERVAL '4 days'),
    (4, CURRENT_TIMESTAMP - INTERVAL '3 days'),
    (5, CURRENT_TIMESTAMP - INTERVAL '2 days');

-- 5. Добавляем события (используя существующие города и временные слоты)
INSERT INTO events (name, city_id, time_slot_id, date, status)
VALUES 
    ('Встреча в Варшаве в пятницу', 1, 3, CURRENT_DATE + INTERVAL '7 days', 'active'),  -- Варшава, пятница 17:00
    ('Встреча в Кракове в понедельник', 2, 4, CURRENT_DATE + INTERVAL '10 days', 'active'),  -- Краков, понедельник 20:00
    ('Встреча в Варшаве в воскресенье', 1, 5, CURRENT_DATE + INTERVAL '14 days', 'active'),  -- Варшава, воскресенье 17:00
    ('Встреча в Кракове в пятницу', 2, 1, CURRENT_DATE + INTERVAL '21 days', 'active');  -- Краков, пятница 19:00

-- 6. Создаем заявки на события для пользователей
INSERT INTO event_applications (application_id, event_id, status, admin_notes, created_at)
VALUES 
    (1, 1, 'pending', NULL, CURRENT_TIMESTAMP - INTERVAL '6 days'),
    (2, 2, 'pending', NULL, CURRENT_TIMESTAMP - INTERVAL '5 days'),
    (3, 3, 'pending', NULL, CURRENT_TIMESTAMP - INTERVAL '4 days'),
    (4, 4, 'pending', NULL, CURRENT_TIMESTAMP - INTERVAL '3 days'),
    (5, 1, 'pending', NULL, CURRENT_TIMESTAMP - INTERVAL '2 days');

-- 7. Добавляем ответы на вопросы
INSERT INTO user_answers (user_id, question_id, answer, answered_at)
VALUES 
    (1, 1, 'Путешествия по миру и знакомство с новыми людьми.', CURRENT_TIMESTAMP - INTERVAL '6 days'),
    (1, 2, '28 лет', CURRENT_TIMESTAMP - INTERVAL '6 days'),
    (2, 1, 'Чтение книг и изучение истории.', CURRENT_TIMESTAMP - INTERVAL '5 days'),
    (2, 2, '32 года', CURRENT_TIMESTAMP - INTERVAL '5 days'),
    (3, 1, 'Спорт и здоровый образ жизни.', CURRENT_TIMESTAMP - INTERVAL '4 days'),
    (3, 2, '25 лет', CURRENT_TIMESTAMP - INTERVAL '4 days'),
    (4, 1, 'Кулинария и изучение разных кухонь мира.', CURRENT_TIMESTAMP - INTERVAL '3 days'),
    (4, 2, '30 лет', CURRENT_TIMESTAMP - INTERVAL '3 days'),
    (5, 1, 'Музыка и игра на гитаре.', CURRENT_TIMESTAMP - INTERVAL '2 days'),
    (5, 2, '35 лет', CURRENT_TIMESTAMP - INTERVAL '2 days');

-- Фиксируем транзакцию
COMMIT;

-- Проверяем результат
SELECT u.id, u.name, u.surname, u.status, a.id as application_id, ea.id as event_application_id, 
       ea.status as application_status, e.id as event_id, e.name as event_name, 
       c.name as city_name, t.day_of_week, t.time
FROM users u
JOIN applications a ON u.id = a.user_id
JOIN event_applications ea ON a.id = ea.application_id
JOIN events e ON ea.event_id = e.id
JOIN cities c ON e.city_id = c.id
JOIN timeslots t ON e.time_slot_id = t.id
ORDER BY u.id; 