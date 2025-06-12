import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Set up logger
logger = logging.getLogger(__name__)

from database.db import add_user, get_user, get_active_questions, add_user_answer, get_user_answers
from user_bot.states import RegistrationStates

# Create router
router = Router()

# --- ТЕКСТЫ ДЛЯ ГЛАВНОГО МЕНЮ ---
MAIN_MENU_TEXT_REGISTERED = "С возвращением, /apply! Вы уже зарегистрированы."

# --- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ: ГЛАВНОЕ МЕНЮ ---
def get_main_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Подать заявку", callback_data="main_apply")
    builder.button(text="📅 Мои встречи", callback_data="main_meetings")
    builder.button(text="👤 Профиль", callback_data="main_profile")
    builder.button(text="❓ Помощь", callback_data="main_help")
    builder.adjust(2)
    return builder.as_markup()

# --- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ: ПОКАЗ ГЛАВНОГО МЕНЮ (без приветствия, с user_id) ---
async def show_main_menu(message, state, user_id=None):
    if user_id is None:
        user_id = message.from_user.id
    user = await get_user(user_id)
    logger.info(f"show_main_menu: user_id={user_id}, user={user}")
    if user:
        logger.info(f"show_main_menu: user['name'] = {user.get('name')}")
        await message.answer(
            "Главное меню",
            reply_markup=get_main_menu()
        )
        return
    await message.answer(
        "Добро пожаловать в 5 Chairs! 🪑🪑🪑🪑🪑\n\n"
        "Этот бот поможет найти и посетить офлайн-встречи с единомышленниками.\n\n"
        "Давайте начнём регистрацию. Как вас зовут?"
    )
    await state.set_state(RegistrationStates.name)

# --- /start ---
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username
    logger.info(f"/start: user_id={user_id}, username={username}")
    user = await get_user(user_id)
    logger.info(f"/start: get_user({user_id}) -> {user}")
    if user:
        logger.info(f"/start: user['name'] = {user.get('name')}")
        await message.answer(
            "Главное меню",
            reply_markup=get_main_menu()
        )
        return
    await message.answer(
        "Добро пожаловать в 5 Chairs! 🪑🪑🪑🪑🪑\n\n"
        "Этот бот поможет найти и посетить офлайн-встречи с единомышленниками.\n\n"
        "Давайте начнём регистрацию. Как вас зовут?"
    )
    await state.set_state(RegistrationStates.name)

# --- /menu ---
@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext):
    await show_main_menu(message, state)

# --- CALLBACK: Главное меню (универсальный возврат) ---
@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    last_msg_id = data.get("last_private_message_id")
    if last_msg_id:
        try:
            await callback.bot.delete_message(callback.message.chat.id, last_msg_id)
        except Exception:
            pass
        await state.update_data(last_private_message_id=None)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await show_main_menu(callback.message, state, user_id=callback.from_user.id)

# --- CALLBACK: Подача заявки (заглушка, переход к FSM реализуется в application.py) ---
@router.callback_query(F.data == "main_apply")
async def cb_apply(callback: CallbackQuery, state: FSMContext):
    from user_bot.handlers.application import start_application
    await start_application(callback, state, is_callback=True)

# --- CALLBACK: Мои встречи (заглушка, переход к meetings реализуется в meetings.py) ---
@router.callback_query(F.data == "main_meetings")
async def cb_meetings(callback: CallbackQuery, state: FSMContext):
    from user_bot.handlers.meetings import cmd_meetings
    await cmd_meetings(callback, state, is_callback=True)

# --- CALLBACK: Профиль (заглушка) ---
@router.callback_query(F.data == "main_profile")
async def cb_profile(callback: CallbackQuery, state: FSMContext):
    from database.db import get_user, get_active_questions, get_user_answers
    user_id = callback.from_user.id
    user = await get_user(user_id)
    if not user:
        msg = await callback.message.edit_text("Профиль не найден. Пожалуйста, зарегистрируйтесь через /start.", reply_markup=get_main_menu())
        await state.update_data(last_private_message_id=msg.message_id)
        return
    text = f"👤 Ваш профиль:\n\n"
    text += f"Имя: {user.get('name', '-') }\n"
    text += f"Фамилия: {user.get('surname', '-') }\n"
    text += f"Возраст: {user.get('age', '-') }\n"
    # Получаем вопросы и ответы
    questions = await get_active_questions()
    answers_list = await get_user_answers(user_id)
    answers = {a['question_id']: a['answer'] for a in answers_list} if answers_list else {}
    if questions:
        text += "\nВаши ответы на вопросы анкеты:\n"
        for q in questions:
            answer = answers.get(q['id'], '—')
            text += f"\n{q['text']}\n — {answer}\n"
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Редактировать анкету", callback_data="profile_edit")
    builder.button(text="В меню", callback_data="main_menu")
    builder.adjust(1)
    msg = await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await state.update_data(last_private_message_id=msg.message_id)

# --- CALLBACK: Мои заявки (заглушка) ---
@router.callback_query(F.data == "main_applications")
async def cb_applications(callback: CallbackQuery, state: FSMContext):
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ В меню", callback_data="main_profile")
    builder.adjust(1)
    await callback.message.edit_text(
        "📨 Мои заявки\n\n(Раздел в разработке)",
        reply_markup=builder.as_markup()
    )

# --- CALLBACK: Помощь (заглушка) ---
@router.callback_query(F.data == "main_help")
async def cb_help(callback: CallbackQuery, state: FSMContext):
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ В меню", callback_data="main_profile")
    builder.adjust(1)
    await callback.message.edit_text(
        "❓ Помощь\n\nЗдесь будет справка по использованию бота.",
        reply_markup=builder.as_markup()
    )

# --- CALLBACK: Редактирование ответа (заглушка) ---
@router.callback_query(F.data == "profile_edit")
async def cb_profile_edit(callback: CallbackQuery, state: FSMContext):
    from database.db import get_active_questions, get_user_answers
    user_id = callback.from_user.id
    questions = await get_active_questions()
    answers_list = await get_user_answers(user_id)
    answers = {a['question_id']: a['answer'] for a in answers_list} if answers_list else {}
    text = "✏️ Редактировать анкету:\n\nВыберите вопрос для изменения ответа:"
    builder = InlineKeyboardBuilder()
    for q in questions:
        ans = answers.get(q['id'], '—')
        builder.button(text=q['text'], callback_data=f"edit_answer_{q['id']}")
    builder.button(text="⬅️ Назад", callback_data="main_profile")
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup())

# Cancel command handler for registration
@router.message(Command("cancel"))
async def cmd_cancel_registration(message: Message, state: FSMContext):
    # Get current state
    current_state = await state.get_state()
    
    # Check if user is in registration process
    if current_state in [RegistrationStates.name, RegistrationStates.surname, RegistrationStates.age]:
        await message.answer(
            "Registration cancelled. You can start again with /start when you're ready."
        )
        # Clear state
        await state.clear()
    else:
        await message.answer(
            "You're not in the registration process. Use /help to see available commands."
        )

# Name handler
@router.message(RegistrationStates.name)
async def process_name(message: Message, state: FSMContext):
    # Check for cancel command
    if message.text.lower() == "cancel":
        await message.answer(
            "Registration cancelled. You can start again with /start when you're ready."
        )
        # Clear state
        await state.clear()
        return
    
    # Save name to state
    await state.update_data(name=message.text)
    
    # Ask for surname
    await message.answer(
        "Great! Now, what's your surname?\n\n"
        "You can type 'cancel' at any time to cancel registration."
    )
    
    # Set state to wait for surname
    await state.set_state(RegistrationStates.surname)

# Surname handler
@router.message(RegistrationStates.surname)
async def process_surname(message: Message, state: FSMContext):
    # Check for cancel command
    if message.text.lower() == "cancel":
        await message.answer(
            "Registration cancelled. You can start again with /start when you're ready."
        )
        # Clear state
        await state.clear()
        return
    
    # Save surname to state
    await state.update_data(surname=message.text)
    
    # Ask for age
    await message.answer(
        "Now, how old are you? (Please enter a number between 18 and 100)\n\n"
        "You can type 'cancel' at any time to cancel registration."
    )
    
    # Set state to wait for age
    await state.set_state(RegistrationStates.age)

# Age handler
@router.message(RegistrationStates.age)
async def process_age(message: Message, state: FSMContext):
    # Check for cancel command
    if message.text.lower() == "cancel":
        await message.answer(
            "Registration cancelled. You can start again with /start when you're ready."
        )
        # Clear state
        await state.clear()
        return
    
    # Validate age
    if not message.text.isdigit():
        await message.answer(
            "Please enter a valid number for your age.\n"
            "You can type 'cancel' to cancel registration."
        )
        return
    
    age = int(message.text)
    if age < 18 or age > 100:
        await message.answer(
            "Please enter a valid age between 18 and 100.\n"
            "You can type 'cancel' to cancel registration."
        )
        return
    
    # Save age to state
    await state.update_data(age=age)
    
    # Create user record in database BEFORE asking questions
    user_id = message.from_user.id
    username = message.from_user.username
    data = await state.get_data()
    
    try:
        # Save user to database first to avoid foreign key violations
        await add_user(
            user_id=user_id,
            username=username,
            name=data['name'],
            surname=data['surname'],
            age=data['age']
        )
        logger.info(f"User {user_id} registered successfully before answering questions")
    except Exception as e:
        # Log the error
        logger.error(f"Failed to register user {user_id} before questions: {e}")
        
        # Inform the user
        await message.answer(
            "Sorry, there was an error during registration. Please try again later or contact support."
        )
        
        # Clear state
        await state.clear()
        return
    
    # Get questions for registration
    questions = await get_active_questions()
    
    if not questions:
        # If no questions, complete registration without questions
        await complete_final_steps(message, state)
        return
    
    # Save questions to state
    await state.update_data(
        questions=[(q['id'], q['text']) for q in questions],
        current_question_index=0
    )
    
    # Get first question
    data = await state.get_data()
    question_id, question_text = data['questions'][0]
    
    await message.answer(
        "Great! Now, please answer a few questions to help us match you with like-minded people.\n\n"
        f"Question 1/{len(data['questions'])}:\n{question_text}"
    )
    
    # Set state to wait for question answers
    await state.set_state(RegistrationStates.questions)

# Questions handler
@router.message(RegistrationStates.questions)
async def process_question_answer(message: Message, state: FSMContext):
    # Check for cancel command
    if message.text.lower() == "cancel":
        await message.answer(
            "Registration cancelled. You can start again with /start when you're ready."
        )
        # Clear state
        await state.clear()
        return
    
    # Get current state data
    data = await state.get_data()
    current_index = data['current_question_index']
    questions = data['questions']
    
    # Save answer to current question
    question_id, _ = questions[current_index]
    user_id = message.from_user.id
    
    try:
        await add_user_answer(user_id, question_id, message.text)
    except Exception as e:
        logger.error(f"Failed to save answer for user {user_id}: {e}")
        # Add more detailed error logging to help diagnose issues
        if "violates foreign key constraint" in str(e):
            logger.error(f"Foreign key violation when saving answer. User {user_id} might not exist in the database.")
        await message.answer(
            "Sorry, there was an error saving your answer. Please try again."
        )
        return
    
    # Move to next question or finish
    current_index += 1
    
    if current_index < len(questions):
        # Update current question index
        await state.update_data(current_question_index=current_index)
        
        # Get next question
        question_id, question_text = questions[current_index]
        
        await message.answer(
            f"Question {current_index + 1}/{len(questions)}:\n{question_text}"
        )
    else:
        # All questions answered, complete the final steps of registration
        await complete_final_steps(message, state)

# Helper function to complete final steps of registration
async def complete_final_steps(message: Message, state: FSMContext):
    data = await state.get_data()
    await message.answer(
        f"Регистрация завершена! Добро пожаловать в 5 Chairs, {data['name']}!\n\n"
        f"Выберите действие в главном меню:",
        reply_markup=get_main_menu()
    )
    await state.clear()

# Help command handler (оставляем для совместимости)
@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "❓ Помощь\n\nЗдесь будет справка по использованию бота.",
        reply_markup=get_main_menu()
    )

# Function to register handlers with the dispatcher
def register_start_handlers(dp):
    logger.info("Registering start handlers")
    dp.include_router(router)

class ProfileEditStates(StatesGroup):
    waiting_for_answer = State()

@router.callback_query(F.data.startswith("edit_answer_"))
async def cb_edit_answer(callback: CallbackQuery, state: FSMContext):
    question_id = int(callback.data.split("_")[-1])
    await state.update_data(edit_question_id=question_id)
    # Получаем текст вопроса и текущий ответ пользователя
    from database.db import get_active_questions, get_user_answers
    user_id = callback.from_user.id
    questions = await get_active_questions()
    answers_list = await get_user_answers(user_id)
    answers = {a['question_id']: a['answer'] for a in answers_list} if answers_list else {}
    question = next((q for q in questions if q['id'] == question_id), None)
    if not question:
        await callback.message.edit_text("Вопрос не найден.")
        return
    current_answer = answers.get(question_id, '—')
    text = (
        f"{question['text']}\n\n"
        f"Ваш текущий ответ:\n{current_answer}\n\n"
        f"✏️ Введите новый ответ:"
    )
    await callback.message.edit_text(text)
    await state.set_state(ProfileEditStates.waiting_for_answer)

@router.message(ProfileEditStates.waiting_for_answer)
async def process_new_answer(message: Message, state: FSMContext):
    data = await state.get_data()
    question_id = data.get("edit_question_id")
    answer = message.text.strip()
    user_id = message.from_user.id
    from database.db import add_user_answer
    await add_user_answer(user_id, question_id, answer)
    await message.answer("Ответ сохранён!", reply_markup=None)
    # Возвращаем к списку вопросов
    from database.db import get_active_questions, get_user_answers
    questions = await get_active_questions()
    answers_list = await get_user_answers(user_id)
    answers = {a['question_id']: a['answer'] for a in answers_list} if answers_list else {}
    text = "✏️ Редактировать анкету:\n\nВыберите вопрос для изменения ответа:"
    builder = InlineKeyboardBuilder()
    for q in questions:
        ans = answers.get(q['id'], '—')
        builder.button(text=q['text'], callback_data=f"edit_answer_{q['id']}")
    builder.button(text="⬅️ Назад", callback_data="main_profile")
    builder.adjust(1)
    await message.answer(text, reply_markup=builder.as_markup())
    await state.clear()