#!/usr/bin/env python3

import re
import sys

def fix_indentation(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Исправляем проблему с отступами в строках около approve_and_add_to_meeting (примерно 450-464)
    # Ищем блок try с неправильными отступами
    approve_add_pattern = re.compile(r'(    # Add user to meeting\n    try:\n        await add_meeting_member.*?\n)        (logger\.info.*?\n)    (except Exception.*?\n)    (    logger\.error.*?\n)    (    await callback\.message\.edit_text.*?\n)    (    await state\.clear\(\)\n)    (    return\n)', re.DOTALL)
    content = approve_add_pattern.sub(r'\1\2    \3        \4        \5        \6        \7', content)

    # Исправляем проблему с отступами в строках около confirm_create_meeting (примерно 791-800)
    # Ищем асинхронный блок с неправильными отступами
    confirm_create_pattern = re.compile(r'(    try:\n)        (# Создаем новую встречу в базе данных\n)    (async with pool\.acquire\(\) as conn:)', re.DOTALL)
    content = confirm_create_pattern.sub(r'\1        \2        \3', content)

    # Исправляем отступы в строке builder = InlineKeyboardBuilder() в функции enter_meeting_name
    enter_name_pattern = re.compile(r'(    # Предлагаем выбрать место проведения\n)        (builder = InlineKeyboardBuilder\(\))', re.DOTALL)
    content = enter_name_pattern.sub(r'\1    \2', content)

    # Исправляем отступы в строке builder.add(InlineKeyboardButton в функции show_meeting_confirmation
    confirmation_pattern = re.compile(r'(    # Создаем клавиатуру подтверждения\n    builder = InlineKeyboardBuilder\(\)\n)        (builder\.add\(InlineKeyboardButton\()', re.DOTALL)
    content = confirmation_pattern.sub(r'\1    \2', content)

    # Исправляем отступы в строке builder = InlineKeyboardBuilder в функции view_meeting
    view_meeting_pattern = re.compile(r'(    # Создаем клавиатуру для дальнейших действий\n)        (builder = InlineKeyboardBuilder\(\))', re.DOTALL)
    content = view_meeting_pattern.sub(r'\1    \2', content)

    # Исправляем отступы await state.clear() в функции cancel_meeting_creation
    cancel_meeting_pattern = re.compile(r'(    await callback\.message\.edit_text\(\n        "Создание встречи отменено. Пользователь остается одобренным, но не добавлен в встречу."\n    \)\n)        (await state\.clear\(\))', re.DOTALL)
    content = cancel_meeting_pattern.sub(r'\1    \2', content)

    # Записываем исправленный контент обратно в файл
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Исправления внесены в файл {file_path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Использование: python fix_indentation.py <путь_к_файлу>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    fix_indentation(file_path) 