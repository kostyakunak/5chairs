from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import is_admin, add_city, get_active_cities, update_city, get_city
from admin_bot.states import CityManagementStates

# Create router
router = Router()

# Cities command handler
@router.message(Command("cities"))
async def cmd_cities(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Check if user is an admin
    if not await is_admin(user_id):
        await message.answer(
            "Sorry, you are not authorized to use this command."
        )
        return
    
    # Create city management keyboard
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Add City"), KeyboardButton(text="Edit City")],
            [KeyboardButton(text="List Cities"), KeyboardButton(text="Back to Menu")]
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        "City Management\n\n"
        "Here you can manage the cities available for users to select in their applications.",
        reply_markup=keyboard
    )

# Add city handler
@router.message(F.text == "Add City")
async def add_city_command(message: Message, state: FSMContext):
    # Check if user is an admin
    if not await is_admin(message.from_user.id):
        return
    
    await message.answer(
        "Please enter the name of the city you want to add:"
    )
    
    # Set state to wait for city name
    await state.set_state(CityManagementStates.add_city)

# Process add city
@router.message(CityManagementStates.add_city)
async def process_add_city(message: Message, state: FSMContext):
    city_name = message.text.strip()
    
    # Validate city name
    if not city_name:
        await message.answer("City name cannot be empty. Please try again:")
        return
    
    # Add city to database
    try:
        city_id = await add_city(city_name)
        
        # Create city management keyboard
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Add City"), KeyboardButton(text="Edit City")],
                [KeyboardButton(text="List Cities"), KeyboardButton(text="Back to Menu")]
            ],
            resize_keyboard=True
        )
        
        await message.answer(
            f"City '{city_name}' has been added successfully!",
            reply_markup=keyboard
        )
    except Exception as e:
        await message.answer(
            f"Failed to add city: {str(e)}\n"
            f"The city might already exist."
        )
    
    # Clear state
    await state.clear()

# List cities handler
@router.message(F.text == "List Cities")
async def list_cities(message: Message, state: FSMContext):
    # Check if user is an admin
    if not await is_admin(message.from_user.id):
        return
    
    # Get cities from database
    cities = await get_active_cities()
    
    if not cities:
        await message.answer("There are no cities in the database.")
        return
    
    # Display cities
    response = "Available Cities:\n\n"
    
    for i, city in enumerate(cities, 1):
        response += f"{i}. {city['name']} (ID: {city['id']})\n"
    
    await message.answer(response)

# Edit city handler
@router.message(F.text == "Edit City")
async def edit_city_command(message: Message, state: FSMContext):
    # Check if user is an admin
    if not await is_admin(message.from_user.id):
        return
    
    # Get cities from database
    cities = await get_active_cities()
    
    if not cities:
        await message.answer("There are no cities to edit.")
        return
    
    # Create city selection keyboard
    builder = InlineKeyboardBuilder()
    for city in cities:
        builder.add(InlineKeyboardButton(
            text=city['name'],
            callback_data=f"edit_city_{city['id']}"
        ))
    builder.adjust(2)
    
    await message.answer(
        "Select a city to edit:",
        reply_markup=builder.as_markup()
    )
    
    # Set state to wait for city selection
    await state.set_state(CityManagementStates.select_city_to_edit)

# City selection for editing handler
@router.callback_query(CityManagementStates.select_city_to_edit, F.data.startswith("edit_city_"))
async def process_city_selection_for_edit(callback: CallbackQuery, state: FSMContext):
    # Extract city ID from callback data
    city_id = int(callback.data.split("_")[2])
    
    # Save city ID to state
    await state.update_data(city_id=city_id)
    
    # Get city for confirmation
    city = await get_city(city_id)
    
    # Create edit options keyboard
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="Rename City",
        callback_data=f"rename_city_{city_id}"
    ))
    builder.add(InlineKeyboardButton(
        text=f"{'Deactivate' if city['active'] else 'Activate'} City",
        callback_data=f"toggle_city_{city_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="Cancel",
        callback_data="cancel_city_edit"
    ))
    builder.adjust(1)
    
    await callback.message.edit_text(
        f"Editing city: {city['name']}\n"
        f"Status: {'Active' if city['active'] else 'Inactive'}\n\n"
        f"What would you like to do?",
        reply_markup=builder.as_markup()
    )

# Rename city handler
@router.callback_query(F.data.startswith("rename_city_"))
async def rename_city(callback: CallbackQuery, state: FSMContext):
    # Extract city ID from callback data
    city_id = int(callback.data.split("_")[2])
    
    # Save city ID to state
    await state.update_data(city_id=city_id)
    
    # Get city for confirmation
    city = await get_city(city_id)
    
    await callback.message.edit_text(
        f"Please enter a new name for the city '{city['name']}':"
    )
    
    # Set state to wait for new city name
    await state.set_state(CityManagementStates.edit_city)

# Process city rename
@router.message(CityManagementStates.edit_city)
async def process_rename_city(message: Message, state: FSMContext):
    # Get city ID from state
    data = await state.get_data()
    city_id = data['city_id']
    
    # Get city for confirmation
    old_city = await get_city(city_id)
    
    # Update city in database
    new_name = message.text.strip()
    
    # Validate city name
    if not new_name:
        await message.answer("City name cannot be empty. Please try again:")
        return
    
    try:
        await update_city(city_id, name=new_name)
        
        # Create city management keyboard
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Add City"), KeyboardButton(text="Edit City")],
                [KeyboardButton(text="List Cities"), KeyboardButton(text="Back to Menu")]
            ],
            resize_keyboard=True
        )
        
        await message.answer(
            f"City name has been updated from '{old_city['name']}' to '{new_name}'!",
            reply_markup=keyboard
        )
    except Exception as e:
        await message.answer(
            f"Failed to update city: {str(e)}\n"
            f"The city name might already exist."
        )
    
    # Clear state
    await state.clear()

# Toggle city active status handler
@router.callback_query(F.data.startswith("toggle_city_"))
async def toggle_city_status(callback: CallbackQuery, state: FSMContext):
    # Extract city ID from callback data
    city_id = int(callback.data.split("_")[2])
    
    # Get city for confirmation
    city = await get_city(city_id)
    
    # Toggle active status
    new_status = not city['active']
    
    # Update city in database
    await update_city(city_id, active=new_status)
    
    # Create city management keyboard
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Add City"), KeyboardButton(text="Edit City")],
            [KeyboardButton(text="List Cities"), KeyboardButton(text="Back to Menu")]
        ],
        resize_keyboard=True
    )
    
    await callback.message.edit_text(
        f"City '{city['name']}' has been {'activated' if new_status else 'deactivated'}!"
    )
    
    await callback.message.answer(
        "What would you like to do next?",
        reply_markup=keyboard
    )
    
    # Clear state
    await state.clear()

# Cancel city edit handler
@router.callback_query(F.data == "cancel_city_edit")
async def cancel_city_edit(callback: CallbackQuery, state: FSMContext):
    # Create city management keyboard
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Add City"), KeyboardButton(text="Edit City")],
            [KeyboardButton(text="List Cities"), KeyboardButton(text="Back to Menu")]
        ],
        resize_keyboard=True
    )
    
    await callback.message.edit_text("City editing cancelled.")
    
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
def register_cities_handlers(dp):
    dp.include_router(router)