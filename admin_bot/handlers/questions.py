from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import is_admin, add_question, get_active_questions, get_question, update_question
from admin_bot.states import QuestionManagementStates

# Create router
router = Router()

# Questions command handler
@router.message(Command("questions"))
async def cmd_questions(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Check if user is an admin
    if not await is_admin(user_id):
        await message.answer(
            "Sorry, you are not authorized to use this command."
        )
        return
    
    # Create question management keyboard
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Add Question"), KeyboardButton(text="Edit Question")],
            [KeyboardButton(text="List Questions"), KeyboardButton(text="Back to Menu")]
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        "Question Management\n\n"
        "Here you can manage the questions that users will answer in their applications.",
        reply_markup=keyboard
    )

# Add question handler
@router.message(F.text == "Add Question")
async def add_question_command(message: Message, state: FSMContext):
    # Check if user is an admin
    if not await is_admin(message.from_user.id):
        return
    await message.answer(
        "Пожалуйста, введите текст вопроса, который вы хотите добавить:"
    )
    # Set state to wait for question text
    await state.set_state(QuestionManagementStates.add_question)

# Process add question (автоматический display_order)
@router.message(QuestionManagementStates.add_question)
async def process_add_question(message: Message, state: FSMContext):
    question_text = message.text.strip()
    if not question_text:
        await message.answer("Текст вопроса не может быть пустым. Пожалуйста, попробуйте ещё раз:")
        return
    # Получаем максимальный display_order среди активных вопросов
    questions = await get_active_questions()
    if questions:
        max_order = max(q['display_order'] for q in questions)
        next_order = max_order + 1
    else:
        next_order = 1
    # Добавляем вопрос с автоматически присвоенным порядком
    try:
        question_id = await add_question(question_text, next_order)
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Add Question"), KeyboardButton(text="Edit Question")],
                [KeyboardButton(text="List Questions"), KeyboardButton(text="Back to Menu")]
            ],
            resize_keyboard=True
        )
        await message.answer(
            f"Вопрос успешно добавлен!\n\nТекст: {question_text}\nПорядковый номер (display order): {next_order}",
            reply_markup=keyboard
        )
    except Exception as e:
        await message.answer(f"Не удалось добавить вопрос: {str(e)}")
    await state.clear()

# List questions handler
@router.message(F.text == "List Questions")
async def list_questions(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    questions = await get_active_questions()
    if not questions:
        await message.answer("There are no questions in the database.")
        return
    # Display questions с обычной нумерацией
    response = "Available Questions:\n\n"
    for i, question in enumerate(questions, 1):
        response += f"{i}. {question['text']}\n"
    await message.answer(response)

# Edit question handler
@router.message(F.text == "Edit Question")
async def edit_question_command(message: Message, state: FSMContext):
    # Check if user is an admin
    if not await is_admin(message.from_user.id):
        return
    
    # Get questions from database
    questions = await get_active_questions()
    
    if not questions:
        await message.answer("There are no questions to edit.")
        return
    
    # Create question selection keyboard
    builder = InlineKeyboardBuilder()
    for question in questions:
        # Truncate question text if too long
        display_text = question['text']
        if len(display_text) > 30:
            display_text = display_text[:27] + "..."
        
        builder.add(InlineKeyboardButton(
            text=f"{question['display_order']}. {display_text}",
            callback_data=f"edit_question_{question['id']}"
        ))
    # Кнопка для изменения порядка
    builder.add(InlineKeyboardButton(
        text="Изменить порядок вопросов",
        callback_data="reorder_questions"
        ))
    builder.adjust(1)
    
    await message.answer(
        "Select a question to edit:",
        reply_markup=builder.as_markup()
    )
    
    # Set state to wait for question selection
    await state.set_state(QuestionManagementStates.select_question_to_edit)

# Question selection for editing handler
@router.callback_query(QuestionManagementStates.select_question_to_edit, F.data.startswith("edit_question_"))
async def process_question_selection_for_edit(callback: CallbackQuery, state: FSMContext):
    # Extract question ID from callback data
    question_id = int(callback.data.split("_")[2])
    # Save question ID to state
    await state.update_data(question_id=question_id)
    # Get question for confirmation
    question = await get_question(question_id)
    # Create edit options keyboard
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="Edit Question Text",
        callback_data=f"edit_text_{question_id}"
    ))
    # Убираем кнопку Edit Display Order
    builder.add(InlineKeyboardButton(
        text=f"{'Deactivate' if question['active'] else 'Activate'} Question",
        callback_data=f"toggle_question_{question_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="Cancel",
        callback_data="cancel_question_edit"
    ))
    builder.adjust(1)
    await callback.message.edit_text(
        f"Editing question:\n\n"
        f"Text: {question['text']}\n"
        f"Display Order: {question['display_order']}\n"
        f"Status: {'Active' if question['active'] else 'Inactive'}\n\n"
        f"What would you like to do?",
        reply_markup=builder.as_markup()
    )

# Edit question text handler
@router.callback_query(F.data.startswith("edit_text_"))
async def edit_question_text(callback: CallbackQuery, state: FSMContext):
    # Extract question ID from callback data
    question_id = int(callback.data.split("_")[2])
    
    # Save question ID to state
    await state.update_data(question_id=question_id)
    
    # Get question for confirmation
    question = await get_question(question_id)
    
    await callback.message.edit_text(
        f"Current question text:\n{question['text']}\n\n"
        f"Please enter the new text for this question:"
    )
    
    # Set state to wait for new question text
    await state.set_state(QuestionManagementStates.edit_question)

# Process question text edit
@router.message(QuestionManagementStates.edit_question)
async def process_edit_question(message: Message, state: FSMContext):
    # Get question ID from state
    data = await state.get_data()
    question_id = data['question_id']
    
    # Get question for confirmation
    old_question = await get_question(question_id)
    
    # Update question in database
    new_text = message.text.strip()
    
    # Validate question text
    if not new_text:
        await message.answer("Question text cannot be empty. Please try again:")
        return
    
    try:
        await update_question(question_id, text=new_text)
        
        # Create question management keyboard
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Add Question"), KeyboardButton(text="Edit Question")],
                [KeyboardButton(text="List Questions"), KeyboardButton(text="Back to Menu")]
            ],
            resize_keyboard=True
        )
        
        await message.answer(
            f"Question text has been updated!",
            reply_markup=keyboard
        )
    except Exception as e:
        await message.answer(
            f"Failed to update question: {str(e)}"
        )
    
    # Clear state
    await state.clear()

# Toggle question active status handler
@router.callback_query(F.data.startswith("toggle_question_"))
async def toggle_question_status(callback: CallbackQuery, state: FSMContext):
    # Extract question ID from callback data
    question_id = int(callback.data.split("_")[2])
    
    # Get question for confirmation
    question = await get_question(question_id)
    
    # Toggle active status
    new_status = not question['active']
    
    # Update question in database
    await update_question(question_id, active=new_status)
    
    # Create question management keyboard
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Add Question"), KeyboardButton(text="Edit Question")],
            [KeyboardButton(text="List Questions"), KeyboardButton(text="Back to Menu")]
        ],
        resize_keyboard=True
    )
    
    await callback.message.edit_text(
        f"Question has been {'activated' if new_status else 'deactivated'}!"
    )
    
    await callback.message.answer(
        "What would you like to do next?",
        reply_markup=keyboard
    )
    
    # Clear state
    await state.clear()

# Cancel question edit handler
@router.callback_query(F.data == "cancel_question_edit")
async def cancel_question_edit(callback: CallbackQuery, state: FSMContext):
    # Create question management keyboard
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Add Question"), KeyboardButton(text="Edit Question")],
            [KeyboardButton(text="List Questions"), KeyboardButton(text="Back to Menu")]
        ],
        resize_keyboard=True
    )
    
    await callback.message.edit_text("Question editing cancelled.")
    
    await callback.message.answer(
        "What would you like to do next?",
        reply_markup=keyboard
    )
    
    # Clear state
    await state.clear()

# Back to menu handler
@router.message(F.text == "Back to Menu")
async def back_to_menu(message: Message, state: FSMContext):
    # Check if user is an admin
    if not await is_admin(message.from_user.id):
        return
    
    # Create admin keyboard
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="/cities"), KeyboardButton(text="/timeslots")],
            [KeyboardButton(text="/questions"), KeyboardButton(text="/applications")],
            [KeyboardButton(text="/meetings"), KeyboardButton(text="/help")]
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        "Main Menu",
        reply_markup=keyboard
    )
    
    # Clear state
    await state.clear()

# Обработка нажатия на "Изменить порядок вопросов"
@router.callback_query(QuestionManagementStates.select_question_to_edit, F.data == "reorder_questions")
async def reorder_questions_start(callback: CallbackQuery, state: FSMContext):
    questions = await get_active_questions()
    if not questions:
        await callback.message.edit_text("Нет вопросов для изменения порядка.")
        return
    builder = InlineKeyboardBuilder()
    for question in questions:
        display_text = question['text']
        if len(display_text) > 30:
            display_text = display_text[:27] + "..."
        builder.add(InlineKeyboardButton(
            text=f"{question['display_order']}. {display_text}",
            callback_data=f"reorder_select_{question['id']}"
        ))
    builder.adjust(1)
    await callback.message.edit_text(
        "Выберите вопрос, который хотите переместить:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(QuestionManagementStates.reorder_questions)

# Обработка выбора вопроса для перестановки
@router.callback_query(QuestionManagementStates.reorder_questions, F.data.startswith("reorder_select_"))
async def reorder_select_question(callback: CallbackQuery, state: FSMContext):
    question_id = int(callback.data.split("_")[-1])
    await state.update_data(reorder_question_id=question_id)
    question = await get_question(question_id)
    # Получаем и выводим список всех вопросов с номерами
    questions = await get_active_questions()
    questions = sorted(questions, key=lambda x: x['display_order'])
    response = "Текущий порядок вопросов:\n"
    for q in questions:
        mark = " ←" if q['id'] == question_id else ""
        response += f"{q['display_order']}. {q['text']}{mark}\n"
    response += f"\nТекущий номер: {question['display_order']}\nВведите новый номер для этого вопроса:"
    await callback.message.edit_text(response)
    await state.set_state(QuestionManagementStates.edit_order)

# Обработка ввода нового номера для перестановки
@router.message(QuestionManagementStates.edit_order)
async def process_reorder_question(message: Message, state: FSMContext):
    data = await state.get_data()
    question_id = data.get('reorder_question_id')
    if not question_id:
        await message.answer("Ошибка: не выбран вопрос для перестановки.")
        await state.clear()
        return
    new_order_text = message.text.strip()
    if not new_order_text.isdigit():
        await message.answer("Порядковый номер должен быть числом. Попробуйте ещё раз:")
        return
    new_order = int(new_order_text)
    if new_order < 1:
        await message.answer("Порядковый номер должен быть положительным числом. Попробуйте ещё раз:")
        return
    # Получаем все вопросы
    questions = await get_active_questions()
    question = next((q for q in questions if q['id'] == question_id), None)
    if not question:
        await message.answer("Вопрос не найден.")
        await state.clear()
        return
    old_order = question['display_order']
    if new_order == old_order:
        await message.answer("Вопрос уже находится на этом месте.")
        await state.clear()
        return
    # Переставляем вопросы
    # Если двигаем вниз (например, с 2 на 4): все между 2 и 4 уменьшаются на 1
    # Если вверх (например, с 4 на 2): все между 2 и 4 увеличиваются на 1
    updates = []
    for q in questions:
        if q['id'] == question_id:
            continue
        if new_order > old_order:
            # вниз
            if old_order < q['display_order'] <= new_order:
                updates.append((q['id'], q['display_order'] - 1))
        else:
            # вверх
            if new_order <= q['display_order'] < old_order:
                updates.append((q['id'], q['display_order'] + 1))
    # Обновляем порядок у затронутых вопросов
    for qid, new_disp in updates:
        await update_question(qid, display_order=new_disp)
    # Обновляем выбранный вопрос
    await update_question(question_id, display_order=new_order)
    # Показываем обновлённый список
    questions = await get_active_questions()
    questions = sorted(questions, key=lambda x: x['display_order'])
    response = "Порядок вопросов успешно изменён!\n\nТекущий порядок вопросов:\n"
    for q in questions:
        response += f"{q['display_order']}. {q['text']}\n"
    await message.answer(response)
    await state.clear()

# Function to register handlers with the dispatcher
def register_questions_handlers(dp):
    dp.include_router(router)