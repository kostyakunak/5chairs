#!/usr/bin/env python3

import asyncio
import sys
import logging
import asyncpg
from datetime import time

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

async def check_time_slots():
    """Проверяет и выводит содержимое таблицы timeslots"""
    # Создаем отдельное соединение для тестирования
    DB_HOST = "localhost"
    DB_PORT = 5432
    DB_NAME = "five_chairs"
    DB_USER = "kostakunak"
    DB_PASSWORD = ""
    
    test_pool = None
    
    try:
        # Создаем соединение с базой данных
        test_pool = await asyncpg.create_pool(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
        )
        
        # Получаем все временные слоты
        async with test_pool.acquire() as conn:
            # Проверяем, существует ли таблица time_slots
            time_slots_exists = await conn.fetchval('''
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'time_slots'
                )
            ''')
            
            if time_slots_exists:
                logger.info("Таблица time_slots существует")
                
                # Получаем все записи из time_slots
                time_slots = await conn.fetch('SELECT * FROM time_slots')
                
                logger.info(f"Найдено {len(time_slots)} временных слотов в таблице time_slots:")
                for slot in time_slots:
                    # Вместо доступа к атрибутам по имени, просто выводим всю запись
                    logger.info(f"Слот: {slot}")
            else:
                logger.info("Таблица time_slots не существует")
                
            # Проверяем, существует ли таблица timeslots (альтернативное название)
            timeslots_exists = await conn.fetchval('''
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'timeslots'
                )
            ''')
            
            if timeslots_exists:
                logger.info("Таблица timeslots существует")
                
                # Получаем все записи из timeslots
                timeslots = await conn.fetch('SELECT * FROM timeslots')
                
                logger.info(f"Найдено {len(timeslots)} временных слотов в таблице timeslots:")
                for slot in timeslots:
                    # Вместо доступа к атрибутам по имени, просто выводим всю запись
                    logger.info(f"Слот: {slot}")
            else:
                logger.info("Таблица timeslots не существует")
            
            # Проверяем схему таблицы time_slots
            if time_slots_exists:
                time_slots_schema = await conn.fetch('''
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = 'time_slots'
                ''')
                
                logger.info("Схема таблицы time_slots:")
                for col in time_slots_schema:
                    logger.info(f"  {col['column_name']}: {col['data_type']}")
            
            # Проверяем, какая таблица используется для внешнего ключа
            meeting_time_slots_fk = await conn.fetch('''
                SELECT
                    ccu.table_name AS foreign_table,
                    ccu.column_name AS foreign_column
                FROM
                    information_schema.table_constraints AS tc
                    JOIN information_schema.key_column_usage AS kcu
                      ON tc.constraint_name = kcu.constraint_name
                      AND tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage AS ccu
                      ON ccu.constraint_name = tc.constraint_name
                      AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name='meeting_time_slots'
            ''')
            
            logger.info("Внешний ключ для таблицы meeting_time_slots указывает на:")
            for fk in meeting_time_slots_fk:
                logger.info(f"Таблица: {fk['foreign_table']}, Колонка: {fk['foreign_column']}")
    except Exception as e:
        logger.error(f"Ошибка при проверке временных слотов: {e}")
    finally:
        # Закрываем соединение
        if test_pool:
            await test_pool.close()

if __name__ == "__main__":
    asyncio.run(check_time_slots()) 