#!/usr/bin/env python3

import asyncio
import sys
import logging
import asyncpg

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

async def add_status_column():
    """Добавляет колонку status в таблицу meeting_members, если она отсутствует"""
    # Параметры подключения к БД
    DB_HOST = "localhost"
    DB_PORT = 5432
    DB_NAME = "five_chairs"
    DB_USER = "kostakunak"
    DB_PASSWORD = ""
    
    conn = None
    
    try:
        # Создаем соединение с базой данных
        conn = await asyncpg.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
        )
        
        # Проверяем, существует ли колонка status в таблице meeting_members
        status_exists = await conn.fetchval('''
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name='meeting_members' AND column_name='status'
            )
        ''')
        
        if status_exists:
            logger.info("Колонка 'status' уже существует в таблице meeting_members")
            return
        
        # Добавляем колонку status
        await conn.execute('''
            ALTER TABLE meeting_members 
            ADD COLUMN status VARCHAR DEFAULT 'confirmed'
        ''')
        
        logger.info("Колонка 'status' успешно добавлена в таблицу meeting_members")
        
        # Проверяем, что колонка действительно добавлена
        status_exists = await conn.fetchval('''
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name='meeting_members' AND column_name='status'
            )
        ''')
        
        if status_exists:
            logger.info("Подтверждено: колонка 'status' теперь существует в таблице meeting_members")
        else:
            logger.error("Колонка 'status' не была добавлена в таблицу meeting_members")
        
    except Exception as e:
        logger.error(f"Ошибка при добавлении колонки status: {e}")
    finally:
        # Закрываем соединение
        if conn:
            await conn.close()
            logger.info("Соединение с базой данных закрыто")

if __name__ == "__main__":
    asyncio.run(add_status_column()) 