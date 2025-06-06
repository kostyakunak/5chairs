# План внедрения изменений по замечаниям пользователя

## 1. Переименование "групп" во "встречи"
- [ ] Заменить все упоминания "группа"/"group" на "встреча"/"meeting" во всех моделях, обработчиках, интерфейсах, текстах, кнопках и документации (как на русском, так и на английском).
- [ ] Проверить и переименовать соответствующие таблицы и поля в базе данных, если требуется.
- [ ] Обновить все связанные команды, callback_data, состояния FSM и переменные.

## 2. Изменение логики взаимодействия с датами и временем (админ-бот)
- [ ] Вынести настройку доступных дней недели и времени для встреч в отдельный раздел админ-панели.
- [ ] Реализовать возможность для админа задавать список дней недели и времени, которые будут доступны для выбора пользователями при подаче заявки.
- [ ] Пользователь при подаче заявки видит только те дни недели и время, которые выбрал админ.
- [ ] Пользователь может выбрать несколько слотов (день недели + время), которые ему подходят.
- [ ] В заявке пользователя хранить список выбранных слотов.

## 3. Автоматизация генерации дат для встреч
- [ ] Реализовать автоматическое создание слотов дат на 2 недели вперёд для каждого выбранного админом дня недели и времени (например, если выбраны пятница и суббота 19:00, то каждую пятницу и субботу ближайших двух недель создаются слоты).
- [ ] Каждый день система автоматически добавляет новый слот через 2 недели (rolling window), если этот день недели и время входят в список активных.
- [ ] Пользователь при подаче заявки выбирает не конкретную дату, а день недели и время, а система сама сопоставляет это с ближайшими доступными датами.

## 4. Логика создания встреч (ранее групп)
### 4.1. Ручное создание встречи
- [ ] Админ может вручную создать встречу, выбрав день недели и время из доступных.
- [ ] После создания встречи админ может добавить в неё пользователей, которые подали заявки и отметили этот слот как подходящий.
- [ ] Интерфейс для добавления пользователей должен показывать только тех, у кого выбранный слот совпадает с параметрами встречи.

### 4.2. Создание встречи при рассмотрении заявки пользователя
- [ ] При рассмотрении заявки админ видит, какие слоты отметил пользователь.
- [ ] Если уже существуют встречи с совпадающими слотами, админ может добавить пользователя в одну из них (список показывается автоматически).
- [ ] Если подходящих встреч нет, админ может создать новую встречу на основе одного из выбранных пользователем слотов (день недели + время), пользователь сразу добавляется в эту встречу.
- [ ] Все действия должны быть отражены в интерфейсе админа и корректно логироваться.

## 5. Дополнительно
- [ ] Обновить документацию и инструкции для админов и пользователей с учётом новой логики.
- [ ] Провести рефакторинг кода для устранения дублирования и устаревших сущностей (например, group_id → meeting_id и т.д.).
- [ ] Обеспечить обратную совместимость миграций БД, если потребуется.
