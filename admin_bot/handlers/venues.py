import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from database.db import (
    is_admin, get_active_cities, get_city, get_venues_by_city, 
    get_venue, add_venue, update_venue
)
from admin_bot.states import VenueManagementStates

# Set up logger
logger = logging.getLogger(__name__)

# Create router
router = Router()

# Venues command handler
@router.message(Command("venues"))
async def cmd_venues(message: Message, state: FSMContext):
    # Check if user is an admin
    if not await is_admin(message.from_user.id):
        return
    
    # Create venue management keyboard
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Add Venue"), KeyboardButton(text="List Venues")],
            [KeyboardButton(text="Back to Menu")]
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        "Venue Management\n\n"
        "You can add new venues or view existing ones.",
        reply_markup=keyboard
    )
    
    # Clear state
    await state.clear()

# Add venue handler
@router.message(F.text == "Add Venue")
async def add_venue_command(message: Message, state: FSMContext):
    # Check if user is an admin
    if not await is_admin(message.from_user.id):
        return
    
    # Get active cities
    cities = await get_active_cities()
    
    if not cities:
        await message.answer("No active cities found. Please add a city first.")
        return
    
    # Create city selection keyboard
    builder = InlineKeyboardBuilder()
    for city in cities:
        builder.add(InlineKeyboardButton(
            text=city['name'],
            callback_data=f"venue_city_{city['id']}"
        ))
    builder.adjust(2)
    
    await message.answer(
        "Select a city for the new venue:",
        reply_markup=builder.as_markup()
    )
    
    # Set state to wait for city selection
    await state.set_state(VenueManagementStates.select_city)

# City selection handler
@router.callback_query(VenueManagementStates.select_city, F.data.startswith("venue_city_"))
async def process_city_selection(callback: CallbackQuery, state: FSMContext):
    # Extract city ID from callback data
    city_id = int(callback.data.split("_")[2])
    
    # Save city ID to state
    await state.update_data(city_id=city_id)
    
    # Get city for confirmation
    city = await get_city(city_id)
    
    await callback.message.edit_text(
        f"Selected city: {city['name']}\n\n"
        f"Please enter the venue name:"
    )
    
    # Set state to wait for venue name
    await state.set_state(VenueManagementStates.enter_name)

# Venue name handler
@router.message(VenueManagementStates.enter_name)
async def process_venue_name(message: Message, state: FSMContext):
    venue_name = message.text.strip()
    
    # Validate venue name
    if not venue_name:
        await message.answer("Venue name cannot be empty. Please try again:")
        return
    
    # Save venue name to state
    await state.update_data(venue_name=venue_name)
    
    await message.answer(
        "Please enter the venue address:"
    )
    
    # Set state to wait for venue address
    await state.set_state(VenueManagementStates.enter_address)

# Venue address handler
@router.message(VenueManagementStates.enter_address)
async def process_venue_address(message: Message, state: FSMContext):
    venue_address = message.text.strip()
    
    # Validate venue address
    if not venue_address:
        await message.answer("Venue address cannot be empty. Please try again:")
        return
    
    # Save venue address to state
    await state.update_data(venue_address=venue_address)
    
    await message.answer(
        "Please enter a description for the venue (optional):"
    )
    
    # Set state to wait for venue description
    await state.set_state(VenueManagementStates.enter_description)

# Venue description handler
@router.message(VenueManagementStates.enter_description)
async def process_venue_description(message: Message, state: FSMContext):
    venue_description = message.text.strip()
    
    # Save venue description to state
    await state.update_data(venue_description=venue_description)
    
    # Get all data from state
    data = await state.get_data()
    
    # Get city for confirmation
    city = await get_city(data['city_id'])
    
    # Format confirmation message
    confirmation = (
        f"Please confirm the venue details:\n\n"
        f"Name: {data['venue_name']}\n"
        f"City: {city['name']}\n"
        f"Address: {data['venue_address']}\n"
        f"Description: {data.get('venue_description', 'None')}\n\n"
        f"Is this correct?"
    )
    
    # Create confirmation keyboard
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Confirm Venue"), KeyboardButton(text="Cancel")]
        ],
        resize_keyboard=True
    )
    
    await message.answer(confirmation, reply_markup=keyboard)
    
    # Set state to wait for confirmation
    await state.set_state(VenueManagementStates.confirm_venue)

# Confirm venue creation
@router.message(VenueManagementStates.confirm_venue, F.text == "Confirm Venue")
async def confirm_venue_creation(message: Message, state: FSMContext):
    # Get all data from state
    data = await state.get_data()
    
    # Create venue in database
    try:
        venue_id = await add_venue(
            name=data['venue_name'],
            address=data['venue_address'],
            city_id=data['city_id'],
            description=data.get('venue_description', None)
        )
        
        # Create venue management keyboard
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Add Venue"), KeyboardButton(text="List Venues")],
                [KeyboardButton(text="Back to Menu")]
            ],
            resize_keyboard=True
        )
        
        await message.answer(
            f"Venue '{data['venue_name']}' has been added successfully!",
            reply_markup=keyboard
        )
        
        # Clear state
        await state.clear()
    except Exception as e:
        await message.answer(
            f"Failed to add venue: {str(e)}"
        )
        
        # Clear state
        await state.clear()

# Cancel venue creation
@router.message(VenueManagementStates.confirm_venue, F.text == "Cancel")
async def cancel_venue_creation(message: Message, state: FSMContext):
    # Create venue management keyboard
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Add Venue"), KeyboardButton(text="List Venues")],
            [KeyboardButton(text="Back to Menu")]
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        "Venue creation cancelled.",
        reply_markup=keyboard
    )
    
    # Clear state
    await state.clear()

# List venues handler
@router.message(F.text == "List Venues")
async def list_venues_command(message: Message, state: FSMContext):
    # Check if user is an admin
    if not await is_admin(message.from_user.id):
        return
    
    # Get active cities
    cities = await get_active_cities()
    
    if not cities:
        await message.answer("No active cities found.")
        return
    
    # Create city selection keyboard
    builder = InlineKeyboardBuilder()
    for city in cities:
        builder.add(InlineKeyboardButton(
            text=city['name'],
            callback_data=f"list_venues_{city['id']}"
        ))
    builder.adjust(2)
    
    await message.answer(
        "Select a city to view venues:",
        reply_markup=builder.as_markup()
    )

# City selection for listing venues
@router.callback_query(F.data.startswith("list_venues_"))
async def list_venues_by_city(callback: CallbackQuery):
    # Extract city ID from callback data
    city_id = int(callback.data.split("_")[2])
    
    # Get city for confirmation
    city = await get_city(city_id)
    
    # Get venues for this city
    venues = await get_venues_by_city(city_id)
    
    if not venues:
        await callback.message.edit_text(
            f"No venues found for {city['name']}."
        )
        return
    
    # Format venues list
    venues_text = f"Venues in {city['name']}:\n\n"
    
    for i, venue in enumerate(venues, 1):
        venues_text += (
            f"{i}. {venue['name']}\n"
            f"   Address: {venue['address']}\n"
            f"   {venue.get('description', '')}\n\n"
        )
    
    # Create back button
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="Back",
        callback_data="back_to_venues"
    ))
    
    await callback.message.edit_text(
        venues_text,
        reply_markup=builder.as_markup()
    )

# Back to venues handler
@router.callback_query(F.data == "back_to_venues")
async def back_to_venues(callback: CallbackQuery):
    await callback.answer()
    
    # Get active cities
    cities = await get_active_cities()
    
    # Create city selection keyboard
    builder = InlineKeyboardBuilder()
    for city in cities:
        builder.add(InlineKeyboardButton(
            text=city['name'],
            callback_data=f"list_venues_{city['id']}"
        ))
    builder.adjust(2)
    
    await callback.message.edit_text(
        "Select a city to view venues:",
        reply_markup=builder.as_markup()
    )

# Back to menu handler
@router.message(F.text == "Back to Menu")
async def back_to_menu(message: Message, state: FSMContext):
    from admin_bot.handlers.start import send_admin_menu
    
    # Clear state
    await state.clear()
    
    # Send admin menu
    await send_admin_menu(message)

# Function to register handlers with the dispatcher
def register_venues_handlers(dp):
    logger.info("Registering venues handlers")
    dp.include_router(router)