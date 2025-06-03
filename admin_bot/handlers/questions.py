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
        "Please enter the text of the question you want to add:"
    )
    
    # Set state to wait for question text
    await state.set_state(QuestionManagementStates.add_question)

# Process add question
@router.message(QuestionManagementStates.add_question)
async def process_add_question(message: Message, state: FSMContext):
    question_text = message.text.strip()
    
    # Validate question text
    if not question_text:
        await message.answer("Question text cannot be empty. Please try again:")
        return
    
    # Save question text to state
    await state.update_data(question_text=question_text)
    
    await message.answer(
        "Please enter the display order for this question (a number):"
    )
    
    # Set state to wait for display order
    await state.set_state(QuestionManagementStates.add_order)

# Process add order
@router.message(QuestionManagementStates.add_order)
async def process_add_order(message: Message, state: FSMContext):
    order_text = message.text.strip()
    
    # Validate order
    if not order_text.isdigit():
        await message.answer("Display order must be a number. Please try again:")
        return
    
    order = int(order_text)
    if order < 1:
        await message.answer("Display order must be a positive number. Please try again:")
        return
    
    # Get question text from state
    data = await state.get_data()
    question_text = data['question_text']
    
    # Add question to database
    try:
        question_id = await add_question(question_text, order)
        
        # Create question management keyboard
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Add Question"), KeyboardButton(text="Edit Question")],
                [KeyboardButton(text="List Questions"), KeyboardButton(text="Back to Menu")]
            ],
            resize_keyboard=True
        )
        
        await message.answer(
            f"Question has been added successfully with display order {order}!",
            reply_markup=keyboard
        )
    except Exception as e:
        await message.answer(
            f"Failed to add question: {str(e)}"
        )
    
    # Clear state
    await state.clear()

# List questions handler
@router.message(F.text == "List Questions")
async def list_questions(message: Message, state: FSMContext):
    # Check if user is an admin
    if not await is_admin(message.from_user.id):
        return
    
    # Get questions from database
    questions = await get_active_questions()
    
    if not questions:
        await message.answer("There are no questions in the database.")
        return
    
    # Display questions
    response = "Available Questions:\n\n"
    
    for i, question in enumerate(questions, 1):
        response += f"{i}. (Order: {question['display_order']}) {question['text']}\n"
    
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
    builder.add(InlineKeyboardButton(
        text="Edit Display Order",
        callback_data=f"edit_order_{question_id}"
    ))
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

# Edit display order handler
@router.callback_query(F.data.startswith("edit_order_"))
async def edit_display_order(callback: CallbackQuery, state: FSMContext):
    # Extract question ID from callback data
    question_id = int(callback.data.split("_")[2])
    
    # Save question ID to state
    await state.update_data(question_id=question_id)
    
    # Get question for confirmation
    question = await get_question(question_id)
    
    await callback.message.edit_text(
        f"Current display order: {question['display_order']}\n\n"
        f"Please enter the new display order for this question (a number):"
    )
    
    # Set state to wait for new display order
    await state.set_state(QuestionManagementStates.edit_order)

# Process display order edit
@router.message(QuestionManagementStates.edit_order)
async def process_edit_order(message: Message, state: FSMContext):
    # Get question ID from state
    data = await state.get_data()
    question_id = data['question_id']
    
    # Get question for confirmation
    old_question = await get_question(question_id)
    
    # Update question in database
    order_text = message.text.strip()
    
    # Validate order
    if not order_text.isdigit():
        await message.answer("Display order must be a number. Please try again:")
        return
    
    order = int(order_text)
    if order < 1:
        await message.answer("Display order must be a positive number. Please try again:")
        return
    
    try:
        await update_question(question_id, display_order=order)
        
        # Create question management keyboard
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Add Question"), KeyboardButton(text="Edit Question")],
                [KeyboardButton(text="List Questions"), KeyboardButton(text="Back to Menu")]
            ],
            resize_keyboard=True
        )
        
        await message.answer(
            f"Display order has been updated from {old_question['display_order']} to {order}!",
            reply_markup=keyboard
        )
    except Exception as e:
        await message.answer(
            f"Failed to update display order: {str(e)}"
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

# Function to register handlers with the dispatcher
def register_questions_handlers(dp):
    dp.include_router(router)