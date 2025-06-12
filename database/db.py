import asyncio
import asyncpg
import logging
import importlib
from datetime import datetime, timedelta, time
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from contextlib import asynccontextmanager

# Import config module
import config
from database.models import Base

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global connection pool for raw SQL queries
pool = None

# SQLAlchemy engines - will be initialized in init_db()
sync_engine = None
async_engine = None

# Session factory will be initialized in init_db()
AsyncSessionLocal = None

@asynccontextmanager
async def get_async_session():
    """Get an async session for SQLAlchemy ORM operations"""
    if AsyncSessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
        
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            raise
        finally:
            await session.close()

async def init_db():
    """Initialize database connection pool and create tables"""
    global pool, sync_engine, async_engine, AsyncSessionLocal
    if pool is None:
        try:
            # Hardcode the database configuration that we know works
            DB_HOST = "localhost"
            DB_PORT = 5432
            DB_NAME = "five_chairs"
            DB_USER = "kostakunak"
            DB_PASSWORD = ""
            
            # Log the database configuration
            logger.info(f"Database configuration: host={DB_HOST}, port={DB_PORT}, name={DB_NAME}, user={DB_USER}")
            
            # Create connection strings at runtime
            SYNC_DB_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
            ASYNC_DB_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
            
            logger.info(f"Using database URL: {ASYNC_DB_URL}")
            
            # Initialize SQLAlchemy engines
            sync_engine = create_engine(SYNC_DB_URL)
            async_engine = create_async_engine(ASYNC_DB_URL)
            
            # Initialize session factory
            AsyncSessionLocal = sessionmaker(
                async_engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Create asyncpg connection pool for raw SQL queries
            pool = await asyncpg.create_pool(
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                min_size=2,  # Reduced from 5 to save resources
                max_size=10,  # Reduced from 20 to save resources
                timeout=30.0  # Added timeout to prevent hanging connections
            )
            logger.info("Database connection pool created")
            logging.getLogger("database.db").info(f"[init_db] pool инициализирован: id={id(pool)}")
            
            # Create tables using SQLAlchemy models
            async with async_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            logger.info("Database tables initialized")
            return pool
        except Exception as e:
            logger.error(f"Failed to create database connection pool: {e}")
            raise
    else:
        logging.getLogger("database.db").info(f"[init_db] pool уже существует: id={id(pool)}")
        return pool

async def close_db():
    """Close database connection pool"""
    global pool
    if pool:
        await pool.close()
        logger.info("Database connection pool closed")
    
    # Close SQLAlchemy engine
    await async_engine.dispose()
    logger.info("SQLAlchemy engine disposed")

# User operations
async def add_user(user_id, username, name, surname, age=None):
    """Add a new user to the database"""
    try:
        async with pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO users (id, username, name, surname, age, registration_date, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (id) DO UPDATE
                SET username = $2, name = $3, surname = $4, age = $5
            ''', user_id, username, name, surname, age, datetime.now(), 'registered')
            logger.info(f"User {user_id} ({name} {surname}) added/updated successfully")
            return True
    except Exception as e:
        logger.error(f"Error adding/updating user {user_id}: {e}")
        # Re-raise the exception to be handled by the caller
        raise

async def get_user(user_id):
    """Get user information from the database"""
    async with pool.acquire() as conn:
        return await conn.fetchrow('SELECT * FROM users WHERE id = $1', user_id)

async def update_user(user_id, **kwargs):
    """Update user information in the database"""
    logger.info(f"[update_user] user_id={user_id}, обновляемые поля: {kwargs}")
    fields = []
    values = []
    for i, (key, value) in enumerate(kwargs.items(), start=1):
        fields.append(f"{key} = ${i}")
        values.append(value)
    if not fields:
        logger.info(f"[update_user] Нет полей для обновления user_id={user_id}")
        return False
    query = f"UPDATE users SET {', '.join(fields)} WHERE id = ${len(values) + 1}"
    values.append(user_id)
    async with pool.acquire() as conn:
        result = await conn.execute(query, *values)
        logger.info(f"[update_user] Результат обновления user_id={user_id}: {result}")
        return True

# City operations
async def add_city(name, active=True):
    """Add a new city to the database"""
    async with pool.acquire() as conn:
        return await conn.fetchval('''
            INSERT INTO cities (name, active)
            VALUES ($1, $2)
            ON CONFLICT (name) DO UPDATE
            SET active = $2
            RETURNING id
        ''', name, active)

async def get_city(city_id):
    """Get city information from the database"""
    async with pool.acquire() as conn:
        return await conn.fetchrow('SELECT * FROM cities WHERE id = $1', city_id)

async def get_active_cities():
    """Get all active cities"""
    async with pool.acquire() as conn:
        return await conn.fetch('SELECT * FROM cities WHERE active = true ORDER BY name')

async def update_city(city_id, **kwargs):
    """Update city information in the database"""
    fields = []
    values = []
    for i, (key, value) in enumerate(kwargs.items(), start=1):
        fields.append(f"{key} = ${i}")
        values.append(value)
    
    if not fields:
        return False
    
    query = f"UPDATE cities SET {', '.join(fields)} WHERE id = ${len(values) + 1}"
    values.append(city_id)
    
    async with pool.acquire() as conn:
        await conn.execute(query, *values)
        return True

# Time slot operations
async def add_timeslot(day_of_week, start_time, end_time=None, city_id=None, active=True):
    """Add a new time slot to the database (теперь обязательно указывать city_id)"""
    if end_time is None:
        if isinstance(start_time, str):
            start_time_obj = datetime.strptime(start_time, '%H:%M').time()
        else:
            start_time_obj = start_time
        end_time = (datetime.combine(datetime.today(), start_time_obj) + timedelta(hours=1)).time()
    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO time_slots (day_of_week, start_time, end_time, city_id, active)
            VALUES ($1, $2, $3, $4, $5)
        ''', day_of_week, start_time, end_time, city_id, active)

async def get_timeslot(time_slot_id):
    """Get time slot information from the database"""
    async with pool.acquire() as conn:
        return await conn.fetchrow('SELECT * FROM time_slots WHERE id = $1', time_slot_id)

async def get_active_timeslots():
    """Get all active time slots"""
    async with pool.acquire() as conn:
        return await conn.fetch('''
            SELECT * FROM time_slots
            WHERE active = true
            ORDER BY CASE
                WHEN day_of_week = 'Monday' THEN 1
                WHEN day_of_week = 'Tuesday' THEN 2
                WHEN day_of_week = 'Wednesday' THEN 3
                WHEN day_of_week = 'Thursday' THEN 4
                WHEN day_of_week = 'Friday' THEN 5
                WHEN day_of_week = 'Saturday' THEN 6
                WHEN day_of_week = 'Sunday' THEN 7
            END, start_time
        ''')

# Time slot management operations
async def update_timeslot(time_slot_id, day_of_week=None, start_time=None, end_time=None, active=None):
    """Update time slot information in the database"""
    fields = []
    values = []
    param_index = 1
    
    # Build the query dynamically based on provided parameters
    if day_of_week is not None:
        fields.append(f"day_of_week = ${param_index}")
        values.append(day_of_week)
        param_index += 1
    
    if start_time is not None:
        fields.append(f"start_time = ${param_index}")
        values.append(start_time)
        param_index += 1
    
    if end_time is not None:
        fields.append(f"end_time = ${param_index}")
        values.append(end_time)
        param_index += 1
    
    if active is not None:
        fields.append(f"active = ${param_index}")
        values.append(active)
        param_index += 1
    
    if not fields:
        return False
    
    # Обновляем поле updated_at при каждом обновлении слота
    fields.append(f"updated_at = ${param_index}")
    values.append(datetime.now())
    param_index += 1
    
    # Add time_slot_id as the last parameter
    values.append(time_slot_id)

    query = f"""
        UPDATE time_slots
        SET {', '.join(fields)}
        WHERE id = ${param_index}
        RETURNING id
    """
    
    async with pool.acquire() as conn:
        result = await conn.fetchval(query, *values)
        return result is not None

async def delete_timeslot(time_slot_id):
    """Delete a time slot (set to inactive)"""
    async with pool.acquire() as conn:
        result = await conn.fetchval('''
            UPDATE time_slots
            SET active = false
            WHERE id = $1
            RETURNING id
        ''', time_slot_id)
        return result is not None

async def assign_timeslot_to_meeting(meeting_id, time_slot_id):
    """Assign a time slot to a meeting"""
    async with pool.acquire() as conn:
        try:
            result = await conn.fetchval('''
                INSERT INTO meeting_time_slots (meeting_id, time_slot_id, created_at)
                VALUES ($1, $2, $3)
                ON CONFLICT (meeting_id, time_slot_id) DO NOTHING
                RETURNING id
            ''', meeting_id, time_slot_id, datetime.now())
            return result is not None
        except Exception as e:
            logger.error(f"Error assigning time slot {time_slot_id} to meeting {meeting_id}: {e}")
            return False

async def remove_timeslot_from_meeting(meeting_id, time_slot_id):
    """Remove a time slot from a meeting"""
    async with pool.acquire() as conn:
        try:
            result = await conn.execute('''
                DELETE FROM meeting_time_slots
                WHERE meeting_id = $1 AND time_slot_id = $2
            ''', meeting_id, time_slot_id)
            return True
        except Exception as e:
            logger.error(f"Error removing time slot {time_slot_id} from meeting {meeting_id}: {e}")
            return False

async def get_meeting_timeslots(meeting_id):
    """Get all time slots assigned to a meeting"""
    async with pool.acquire() as conn:
        return await conn.fetch('''
            SELECT ts.*
            FROM time_slots ts
            JOIN meeting_time_slots mts ON ts.id = mts.time_slot_id
            WHERE mts.meeting_id = $1
            ORDER BY CASE
                WHEN ts.day_of_week = 'Monday' THEN 1
                WHEN ts.day_of_week = 'Tuesday' THEN 2
                WHEN ts.day_of_week = 'Wednesday' THEN 3
                WHEN ts.day_of_week = 'Thursday' THEN 4
                WHEN ts.day_of_week = 'Friday' THEN 5
                WHEN ts.day_of_week = 'Saturday' THEN 6
                WHEN ts.day_of_week = 'Sunday' THEN 7
            END, ts.start_time
        ''', meeting_id)

async def get_meetings_by_timeslot(time_slot_id):
    """Get all meetings that use a specific time slot"""
    async with pool.acquire() as conn:
        return await conn.fetch('''
            SELECT m.*
            FROM meetings m
            JOIN meeting_time_slots mts ON m.id = mts.meeting_id
            WHERE mts.time_slot_id = $1
            ORDER BY m.meeting_date, m.meeting_time
        ''', time_slot_id)

# Question operations
async def add_question(text, display_order, active=True):
    """Add a new question to the database"""
    async with pool.acquire() as conn:
        return await conn.fetchval('''
            INSERT INTO questions (text, display_order, active)
            VALUES ($1, $2, $3)
            RETURNING id
        ''', text, display_order, active)

async def get_question(question_id):
    """Get question information from the database"""
    async with pool.acquire() as conn:
        return await conn.fetchrow('SELECT * FROM questions WHERE id = $1', question_id)

async def get_active_questions():
    """Get all active questions ordered by display_order"""
    async with pool.acquire() as conn:
        return await conn.fetch('SELECT * FROM questions WHERE active = true ORDER BY display_order')

async def update_question(question_id, **kwargs):
    """Update question information in the database"""
    fields = []
    values = []
    for i, (key, value) in enumerate(kwargs.items(), start=1):
        fields.append(f"{key} = ${i}")
        values.append(value)
    
    if not fields:
        return False
    
    query = f"UPDATE questions SET {', '.join(fields)} WHERE id = ${len(values) + 1}"
    values.append(question_id)
    
    async with pool.acquire() as conn:
        await conn.execute(query, *values)
        return True

# User answer operations
async def add_user_answer(user_id, question_id, answer):
    """Add a user answer to the database"""
    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO user_answers (user_id, question_id, answer, answered_at)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id, question_id) DO UPDATE
            SET answer = $3, answered_at = $4
        ''', user_id, question_id, answer, datetime.now())
        return True

async def get_user_answers(user_id):
    """Get all answers for a user with question text"""
    async with pool.acquire() as conn:
        return await conn.fetch('''
            SELECT ua.*, q.text as question_text
            FROM user_answers ua
            JOIN questions q ON ua.question_id = q.id
            WHERE ua.user_id = $1
            ORDER BY q.display_order
        ''', user_id)

# Application operations
async def get_or_create_application(user_id, time_slot_id):
    """Get existing application for this slot or create a new one"""
    async with pool.acquire() as conn:
        return await conn.fetchval('''
            INSERT INTO applications (user_id, time_slot_id, created_at, status)
            VALUES ($1, $2, $3, 'pending')
            ON CONFLICT (user_id, time_slot_id) DO UPDATE
            SET status = 'pending', created_at = $3
            RETURNING id
        ''', user_id, time_slot_id, datetime.now())

# Admin operations
async def add_admin(admin_id, username, name, is_superadmin=False):
    """Add a new admin to the database"""
    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO admins (id, username, name, added_at, is_superadmin)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (id) DO UPDATE
            SET username = $2, name = $3, is_superadmin = $5
        ''', admin_id, username, name, datetime.now(), is_superadmin)
        return True

async def get_admin(admin_id):
    """Get admin information from the database"""
    async with pool.acquire() as conn:
        return await conn.fetchrow('SELECT * FROM admins WHERE id = $1', admin_id)

async def is_admin(user_id):
    """Check if a user is an admin"""
    async with pool.acquire() as conn:
        admin = await conn.fetchrow('SELECT * FROM admins WHERE id = $1', user_id)
        return bool(admin)

async def is_superadmin(user_id):
    """Check if a user is a superadmin"""
    async with pool.acquire() as conn:
        admin = await conn.fetchrow('SELECT * FROM admins WHERE id = $1 AND is_superadmin = true', user_id)
        return bool(admin)

# Venue operations
async def add_venue(name, address, city_id, description=None):
    """Add a new venue to the database"""
    async with pool.acquire() as conn:
        return await conn.fetchval('''
            INSERT INTO venues (name, address, city_id, description, created_at)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
        ''', name, address, city_id, description, datetime.now())

async def get_venues_by_city(city_id):
    """Get all venues for a specific city"""
    async with pool.acquire() as conn:
        return await conn.fetch('''
            SELECT v.*, c.name as city_name
            FROM venues v
            JOIN cities c ON v.city_id = c.id
            WHERE v.city_id = $1 AND v.active = true
            ORDER BY v.name
        ''', city_id)

async def get_venue(venue_id):
    """Get venue information by ID"""
    async with pool.acquire() as conn:
        return await conn.fetchrow('''
            SELECT v.*, c.name as city_name
            FROM venues v
            JOIN cities c ON v.city_id = c.id
            WHERE v.id = $1
        ''', venue_id)

async def add_venue(name, address, city_id, description=None):
    """Add a new venue"""
    async with pool.acquire() as conn:
        venue_id = await conn.fetchval('''
            INSERT INTO venues (name, address, city_id, description, active, created_at)
            VALUES ($1, $2, $3, $4, true, $5)
            RETURNING id
        ''', name, address, city_id, description, datetime.now())
        return venue_id

async def update_venue(venue_id, name=None, address=None, description=None, active=None):
    """Update venue details"""
    async with pool.acquire() as conn:
        # Build update query dynamically based on provided parameters
        update_parts = []
        params = [venue_id]
        param_index = 2
        
        if name is not None:
            update_parts.append(f"name = ${param_index}")
            params.append(name)
            param_index += 1
        
        if address is not None:
            update_parts.append(f"address = ${param_index}")
            params.append(address)
            param_index += 1
        
        if description is not None:
            update_parts.append(f"description = ${param_index}")
            params.append(description)
            param_index += 1
        
        if active is not None:
            update_parts.append(f"active = ${param_index}")
            params.append(active)
            param_index += 1
        
        if not update_parts:
            return False
        
        update_query = f'''
            UPDATE venues
            SET {', '.join(update_parts)}
            WHERE id = $1
            RETURNING id
        '''
        
        updated_id = await conn.fetchval(update_query, *params)
        return updated_id is not None

async def update_venue(venue_id, name=None, address=None, description=None, active=None):
    """Update venue information"""
    async with pool.acquire() as conn:
        # Get current venue data
        venue = await conn.fetchrow('SELECT * FROM venues WHERE id = $1', venue_id)
        if not venue:
            return False
        
        # Update with new values or keep existing ones
        name = name if name is not None else venue['name']
        address = address if address is not None else venue['address']
        description = description if description is not None else venue['description']
        active = active if active is not None else venue['active']
        
        await conn.execute('''
            UPDATE venues
            SET name = $1, address = $2, description = $3, active = $4
            WHERE id = $5
        ''', name, address, description, active, venue_id)
        return True

async def delete_venue(venue_id):
    """Delete a venue (set inactive)"""
    async with pool.acquire() as conn:
        await conn.execute('''
            UPDATE venues
            SET active = false
            WHERE id = $1
        ''', venue_id)
        return True

# Meeting operations (formerly groups)
async def create_meeting(name, meeting_date, meeting_time, city_id, venue, created_by=None, venue_address=None):
    """Create a new meeting in the database"""
    async with pool.acquire() as conn:
        return await conn.fetchval('''
            INSERT INTO meetings (name, meeting_date, meeting_time, city_id, venue, venue_address, status, created_by, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING id
        ''', name, meeting_date, meeting_time, city_id, venue, venue_address, 'planned', created_by, datetime.now())

async def get_meeting(meeting_id):
    """Get meeting information from the database"""
    async with pool.acquire() as conn:
        return await conn.fetchrow('SELECT * FROM meetings WHERE id = $1', meeting_id)

async def get_meetings_by_status(status):
    """Get all meetings with a specific status"""
    async with pool.acquire() as conn:
        return await conn.fetch('''
            SELECT m.*, c.name as city_name
            FROM meetings m
            JOIN cities c ON m.city_id = c.id
            WHERE m.status = $1
            ORDER BY m.meeting_date, m.meeting_time
        ''', status)

async def update_meeting_status(meeting_id, status):
    """Update meeting status in the database"""
    async with pool.acquire() as conn:
        await conn.execute('''
            UPDATE meetings
            SET status = $1, updated_at = NOW()
            WHERE id = $2
        ''', status, meeting_id)
        return True

# Meeting member operations
async def add_meeting_member(meeting_id, user_id, added_by=None):
    """Add a user to a meeting"""
    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO meeting_members (meeting_id, user_id, added_at, added_by)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (meeting_id, user_id) DO NOTHING
        ''', meeting_id, user_id, datetime.now(), added_by)
        return True

async def remove_meeting_member(meeting_id, user_id):
    """Remove a user from a meeting"""
    async with pool.acquire() as conn:
        await conn.execute('''
            DELETE FROM meeting_members
            WHERE meeting_id = $1 AND user_id = $2
        ''', meeting_id, user_id)
        return True

async def get_meeting_members(meeting_id):
    """Get all members of a meeting with user information"""
    async with pool.acquire() as conn:
        return await conn.fetch('''
            SELECT mm.*, u.name, u.surname, u.username
            FROM meeting_members mm
            JOIN users u ON mm.user_id = u.id
            WHERE mm.meeting_id = $1
            ORDER BY mm.added_at
        ''', meeting_id)

async def get_user_meetings(user_id):
    """Get all meetings a user is a member of"""
    async with pool.acquire() as conn:
        return await conn.fetch('''
            SELECT m.*, c.name as city_name
            FROM meetings m
            JOIN meeting_members mm ON m.id = mm.meeting_id
            JOIN cities c ON m.city_id = c.id
            WHERE mm.user_id = $1
            ORDER BY m.meeting_date, m.meeting_time
        ''', user_id)

async def count_meeting_members(meeting_id):
    """Count the number of members in a meeting"""
    async with pool.acquire() as conn:
        return await conn.fetchval('''
            SELECT COUNT(*) FROM meeting_members
            WHERE meeting_id = $1
        ''', meeting_id)
        
# Available Dates operations
async def add_available_date(date, time_slot_id, is_available=True):
    """Add a new available date to the database"""
    async with pool.acquire() as conn:
        return await conn.fetchval('''
            INSERT INTO available_dates (date, time_slot_id, is_available, created_at)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (date, time_slot_id) DO UPDATE
            SET is_available = $3, updated_at = $4
            RETURNING id
        ''', date, time_slot_id, is_available, datetime.now())

async def get_available_date(date_id):
    """Get available date information from the database"""
    async with pool.acquire() as conn:
        return await conn.fetchrow('SELECT * FROM available_dates WHERE id = $1', date_id)

async def get_available_dates(start_date=None, end_date=None):
    """Get all available dates within the specified range"""
    if start_date is None:
        start_date = datetime.now().date()
    
    if end_date is None:
        end_date = start_date + timedelta(days=14)
    
    async with pool.acquire() as conn:
        return await conn.fetch('''
            SELECT ad.*, ts.day_of_week, ts.time
            FROM available_dates ad
            JOIN timeslots ts ON ad.time_slot_id = ts.id
            WHERE ad.date >= $1 AND ad.date <= $2 AND ad.is_available = true
            ORDER BY ad.date, ts.time
        ''', start_date, end_date)

async def get_available_dates_by_city_and_timeslot(city_id, time_slot_id, start_date=None, end_date=None):
    """Get all available dates for a specific city and time slot within the specified range"""
    if start_date is None:
        start_date = datetime.now().date()
    
    if end_date is None:
        end_date = start_date + timedelta(days=14)
    
    async with pool.acquire() as conn:
        # Сначала проверим, существует ли временной слот
        timeslot = None
        try:
            timeslot = await conn.fetchrow('SELECT * FROM time_slots WHERE id = $1', time_slot_id)
        except Exception as e:
            # Если таблица называется по-другому, попробуем другое имя
            if "relation \"time_slots\" does not exist" in str(e):
                try:
                    timeslot = await conn.fetchrow('SELECT * FROM time_slots WHERE id = $1', time_slot_id)
                except Exception as e2:
                    logger.error(f"Не удалось найти таблицу временных слотов: {e2}")
                    return []
            else:
                logger.error(f"Ошибка при проверке временного слота: {e}")
                return []
        
        if not timeslot:
            logger.warning(f"Временной слот с id={time_slot_id} не найден")
            return []
        
        # Теперь получаем доступные даты
        dates = []
        try:
            # Пробуем использовать time_slot_id
            dates = await conn.fetch('''
                SELECT ad.date
                FROM available_dates ad
                WHERE ad.time_slot_id = $1 
                AND ad.date >= $2 
                AND ad.date <= $3 
                AND ad.is_available = true
                ORDER BY ad.date
            ''', time_slot_id, start_date, end_date)
        except Exception as e:
            # Если time_slot_id не существует, используем time_slot_id
            if "column ad.time_slot_id does not exist" in str(e):
                try:
                    dates = await conn.fetch('''
                        SELECT ad.date
                        FROM available_dates ad
                        WHERE ad.time_slot_id = $1 
                        AND ad.date >= $2 
                        AND ad.date <= $3 
                        AND ad.is_available = true
                        ORDER BY ad.date
                    ''', time_slot_id, start_date, end_date)
                except Exception as e2:
                    logger.error(f"Ошибка при получении доступных дат: {e2}")
                    return []
            else:
                logger.error(f"Ошибка при получении доступных дат: {e}")
                return []
        
        return [d['date'] for d in dates]

async def get_available_dates_by_timeslot(time_slot_id, start_date=None, end_date=None):
    """Get all available dates for a specific time slot within the specified range"""
    if start_date is None:
        start_date = datetime.now().date()
    
    if end_date is None:
        end_date = start_date + timedelta(days=14)
    
    async with pool.acquire() as conn:
        return await conn.fetch('''
            SELECT ad.*, ts.day_of_week, ts.time
            FROM available_dates ad
            JOIN timeslots ts ON ad.time_slot_id = ts.id
            WHERE ad.time_slot_id = $1 AND ad.date >= $2 AND ad.date <= $3 AND ad.is_available = true
            ORDER BY ad.date
        ''', time_slot_id, start_date, end_date)

async def update_available_date(date_id, is_available):
    """Update availability status of a date in the database"""
    async with pool.acquire() as conn:
        await conn.execute('''
            UPDATE available_dates
            SET is_available = $1, updated_at = $2
            WHERE id = $3
        ''', is_available, datetime.now(), date_id)
        return True

async def remove_old_available_dates():
    """Remove available dates that are in the past"""
    async with pool.acquire() as conn:
        await conn.execute('''
            DELETE FROM available_dates
            WHERE date < CURRENT_DATE
        ''')
        return True

# --- ЗАГЛУШКИ ДЛЯ ВОССТАНОВЛЕНИЯ РАБОТОСПОСОБНОСТИ ---
# TODO: Реализовать эти функции на новой архитектуре (meetings/applications)

async def get_application(app_id):
    """
    Возвращает заявку по id (applications) с расширенными данными.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow('''
            SELECT 
                a.*, 
                u.name AS user_name, u.surname AS user_surname, u.username AS user_username, u.age AS user_age, u.registration_date,
                ts.id AS timeslot_id, ts.day_of_week, ts.start_time AS time,
                c.id AS city_id, c.name AS city_name
            FROM applications a
            JOIN users u ON a.user_id = u.id
            JOIN time_slots ts ON a.time_slot_id = ts.id
            JOIN cities c ON ts.city_id = c.id
            WHERE a.id = $1
        ''', app_id)
        return dict(row) if row else None

async def update_application_status(app_id, status=None, note=None):
    """
    Обновляет статус заявки (и/или добавляет заметку).
    """
    async with pool.acquire() as conn:
        if status is not None and note is not None:
            await conn.execute('''
                UPDATE applications
                SET status = $1, note = $2
                WHERE id = $3
            ''', status, note, app_id)
        elif status is not None:
            await conn.execute('''
                UPDATE applications
                SET status = $1
                WHERE id = $2
            ''', status, app_id)
        elif note is not None:
            await conn.execute('''
                UPDATE applications
                SET note = $1
                WHERE id = $2
            ''', note, app_id)
        else:
            return False
        return True

async def get_user_application(user_id):
    """
    Возвращает заявку пользователя (applications) с расширенными данными.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow('''
            SELECT 
                a.*, 
                u.name AS user_name, u.surname AS user_surname, u.username AS user_username, u.age AS user_age, u.registration_date,
                ts.id AS timeslot_id, ts.day_of_week, ts.start_time AS time,
                c.id AS city_id, c.name AS city_name
            FROM applications a
            JOIN users u ON a.user_id = u.id
            JOIN time_slots ts ON a.time_slot_id = ts.id
            JOIN cities c ON ts.city_id = c.id
            WHERE a.user_id = $1
        ''', user_id)
        return dict(row) if row else None

async def get_pending_applications():
    """
    Возвращает список всех заявок (applications) со статусом 'pending' с расширенными данными.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT 
                a.*, 
                u.name AS user_name, u.surname AS user_surname, u.username AS user_username, u.age AS user_age, u.registration_date, u.status AS user_status,
                ts.id AS timeslot_id, ts.day_of_week, ts.start_time AS time,
                c.id AS city_id, c.name AS city_name
            FROM applications a
            JOIN users u ON a.user_id = u.id
            JOIN time_slots ts ON a.time_slot_id = ts.id
            JOIN cities c ON ts.city_id = c.id
            WHERE a.status = 'pending' AND u.status != 'rejected'
            ORDER BY a.created_at
        ''')
        return [dict(row) for row in rows]

async def get_pending_applications_by_city(city_id):
    """
    Возвращает все заявки для заданного города со статусом 'pending' с расширенными данными (user, timeslot, city).
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT 
                a.*, 
                u.name AS user_name, u.surname AS user_surname, u.username AS user_username, u.age AS user_age, u.registration_date, u.status AS user_status,
                ts.id AS timeslot_id, ts.day_of_week, ts.start_time AS time,
                c.id AS city_id, c.name AS city_name
            FROM applications a
            JOIN users u ON a.user_id = u.id
            JOIN time_slots ts ON a.time_slot_id = ts.id
            JOIN cities c ON ts.city_id = c.id
            WHERE ts.city_id = $1 AND a.status = 'pending' AND u.status != 'rejected' AND u.status != 'banned'
            ORDER BY a.created_at
        ''', city_id)
        return [dict(row) for row in rows]

async def get_pending_applications_by_timeslot(city_id, time_slot_id):
    """
    Возвращает все заявки для выбранного города и временного слота со статусом 'pending' с расширенными данными (user, timeslot, city).
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT 
                a.*, 
                u.name AS user_name, u.surname AS user_surname, u.username AS user_username, u.age AS user_age, u.registration_date, u.status AS user_status,
                ts.id AS timeslot_id, ts.day_of_week, ts.start_time AS time,
                c.id AS city_id, c.name AS city_name
            FROM applications a
            JOIN users u ON a.user_id = u.id
            JOIN time_slots ts ON a.time_slot_id = ts.id
            JOIN cities c ON ts.city_id = c.id
            WHERE ts.city_id = $1 AND a.time_slot_id = $2 AND a.status = 'pending' AND u.status != 'rejected'
            ORDER BY a.created_at
        ''', city_id, time_slot_id)
        return [dict(row) for row in rows]

async def get_available_dates_with_users_count(city_id, time_slot_id, **kwargs):
    """
    Возвращает список доступных дат для города и временного слота с количеством пользователей на каждую дату.
    Пока реализовано как заглушка. Поддерживает любые лишние аргументы.
    """
    return []

async def get_users_by_time_preference(time_slot_id):
    """
    Возвращает пользователей, подходящих по временному слоту.
    Пока реализовано как заглушка.
    """
    return []

async def get_compatible_users_for_meeting(meeting_id):
    """
    Возвращает пользователей, которых можно добавить во встречу.
    Пока реализовано как заглушка.
    """
    return []

async def create_meeting_from_available_date(date, time_slot_id, city_id, venue_id, created_by=None):
    """
    Создаёт встречу на основе выбранной доступной даты, временного слота, города и площадки.
    Пока реализовано как заглушка.
    """
    return None

async def get_pool():
    global pool
    if pool is None:
        await init_db()
    return pool

async def get_user_applications(user_id):
    """
    Возвращает все заявки пользователя (applications) с расширенными данными по слоту и городу.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT 
                a.*, 
                u.name AS user_name, u.surname AS user_surname, u.username AS user_username, u.age AS user_age, u.registration_date,
                ts.id AS timeslot_id, ts.day_of_week, ts.start_time AS time, ts.end_time,
                c.id AS city_id, c.name AS city_name
            FROM applications a
            JOIN users u ON a.user_id = u.id
            JOIN time_slots ts ON a.time_slot_id = ts.id
            JOIN cities c ON ts.city_id = c.id
            WHERE a.user_id = $1
            ORDER BY a.created_at DESC
        ''', user_id)
        return [dict(row) for row in rows]