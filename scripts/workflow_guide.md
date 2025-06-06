# Руководство по работе сервиса "5 Стульев"

Привет! Это руководство простым языком расскажет, как на самом деле работает наш сервис "5 Стульев" и какая логика заложена в обоих ботах: для пользователей и администраторов.

## Общая логика сервиса

Представь, что ты организуешь серию встреч в разных городах. Вот как это работает:

1. Админ (организатор) заранее определяет, в каких городах, в какие дни и в какое время могут проходить встречи
2. Пользователи видят эти варианты и отмечают, какие дни и время им подходят
3. Админ получает заявки и решает, кого и на какую конкретную встречу пригласить

Важно понимать: пользователь НЕ создаёт встречи и не может самостоятельно "записаться" на определённое время! Он только показывает своё желание поучаствовать и сообщает, какие варианты времени ему подходят.

## Как это работает для пользователя

### Шаг 1: Первое знакомство с ботом
Когда пользователь впервые заходит в бота, он получает приветствие и возможность зарегистрироваться. Регистрация простая: имя, контакты, город.

### Шаг 2: Просмотр доступных мероприятий
После регистрации пользователю становятся доступны команды, в том числе просмотр доступных активностей. Система показывает, в каких городах и когда планируются встречи.

### Шаг 3: Подача заявки
Когда пользователь нажимает кнопку "Apply" (Подать заявку):
- Сначала ему предлагается выбрать город
- Затем показываются доступные дни для этого города
- Потом для каждого выбранного дня показываются доступные временные слоты

**Пример:** Пользователь Вася из Москвы видит, что встречи проходят в пятницу и субботу. Он выбирает оба дня, потому что может в любой из них. Затем он видит доступные слоты: пятница в 18:00 и 19:30, суббота в 12:00. Он отмечает все три варианта, потому что все они ему подходят.

### Шаг 4: Отправка заявки на рассмотрение
После выбора всех подходящих временных слотов, пользователь отправляет заявку. Он видит сообщение об успешной подаче заявки и может только ждать решения администратора.

### Шаг 5: Получение решения
Когда администратор обработает заявку, пользователь получит уведомление о том, принята его заявка или отклонена. Если принята, то ему сообщат точную дату и время конкретной встречи, на которую его определили.

## Как это работает для администратора

### Шаг 1: Настройка доступных временных слотов
Админ сначала добавляет временные слоты, определяя:
- Город проведения
- Дату
- Время начала
- Вместимость (сколько участников может быть)

**Пример:** Админ Маша добавляет слоты "Москва, пятница, 18:00, до 5 человек", "Москва, пятница, 19:30, до 5 человек" и "Москва, суббота, 12:00, до 5 человек".

### Шаг 2: Просмотр заявок пользователей
Когда поступают заявки, админ видит:
- Кто подал заявку (имя, контакты)
- Какие временные слоты выбрал пользователь как подходящие

**Пример:** Админ Маша видит, что пользователь Вася может прийти в любой из трёх предложенных слотов: пятница 18:00, пятница 19:30 или суббота 12:00.

### Шаг 3: Создание конкретных встреч
Админ анализирует заявки и формирует конкретные встречи, распределяя пользователей:
- Создаёт встречу на определённый временной слот
- Добавляет в неё подходящих участников

**Пример:** Маша видит, что на пятницу 18:00 набралось больше всего людей, которым подходит это время. Она создаёт встречу на этот слот и добавляет туда Васю и ещё 4 человек.

### Шаг 4: Уведомление пользователей
После формирования встречи, система автоматически отправляет участникам уведомления о том, на какую конкретную встречу они приглашены.

### Шаг 5: Управление существующими встречами
Админ может:
- Изменять состав участников встречи
- Переносить встречи на другие временные слоты
- Отменять встречи

## Жизненный цикл заявки

1. **Создание**: пользователь выбирает удобные ему временные слоты и отправляет заявку
2. **Ожидание**: заявка находится в статусе "ожидающая рассмотрения"
3. **Рассмотрение**: администратор просматривает заявку и принимает решение
4. **Распределение**: администратор добавляет пользователя в конкретную встречу на один из выбранных им временных слотов
5. **Уведомление**: пользователь получает оповещение о принятом решении
6. **Завершение**: после проведения встречи заявка считается закрытой

## Типичные сценарии и примеры

### Сценарий 1: Идеальный случай
Алиса выбирает три подходящих ей временных слота. Админ видит, что на вторник 17:00 уже есть 4 участника, которым это время подходит. Он добавляет Алису пятым участником на этот слот, и встреча укомплектована.

### Сценарий 2: Нет подходящей встречи
Борис выбирает только один временной слот - четверг 19:00. Но на этот слот уже набрана полная группа. Админ видит, что на другие дни Борис прийти не может, и временно откладывает его заявку до следующей недели, когда планируется новая встреча в четверг.

### Сценарий 3: Изменение планов
Встреча была назначена на пятницу 18:00, но администратор вынужден её отменить. Он отменяет эту встречу и перераспределяет участников на другие доступные временные слоты, которые они отметили как подходящие.

## В чём главная суть сервиса

Мы не просто позволяем людям "забронировать" время - мы создаём гибкую систему, где:

1. Админы могут эффективно формировать полноценные группы
2. Пользователи могут указать несколько удобных вариантов вместо жёсткой привязки к одному времени
3. Система позволяет оптимально распределить участников, учитывая их возможности и ограничения по времени

Главная ценность нашего сервиса - в гибкости и возможности найти оптимальное решение для всех участников процесса!

## Что важно запомнить
- Пользователи НЕ записываются на конкретную встречу, а лишь указывают подходящие варианты
- Временные слоты создаются ТОЛЬКО администраторами
- Решение о том, кто и когда встречается, принимает ТОЛЬКО администратор
- Система помогает собирать оптимальные группы участников на основе их временных предпочтений 