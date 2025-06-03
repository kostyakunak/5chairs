#!/usr/bin/env python3

import sys
import re

def fix_indentation(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Исправляем проблему с отступами в строке # Создаем клавиатуру для дальнейших действий и следующих строках
    content = re.sub(
        r'(        # Создаем клавиатуру для дальнейших действий\n)    (builder = InlineKeyboardBuilder\(\))',
        r'\1        \2',
        content
    )
    
    # Исправляем проблему с отступами в строке builder.add() в функции confirm_create_meeting
    content = re.sub(
        r'(        builder = InlineKeyboardBuilder\(\)\n)        (builder\.add\(InlineKeyboardButton\()',
        r'\1        \2',
        content
    )
    
    # Исправляем проблему с отступами в строке builder.add() в функции confirm_add_user_to_meeting
    content = re.sub(
        r'(        builder = InlineKeyboardBuilder\(\)\n)    (builder\.add\(InlineKeyboardButton\()',
        r'\1        \2',
        content
    )
    
    # Записываем исправленный контент обратно в файл
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Окончательные исправления внесены в файл {file_path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Использование: python fix_final_indentation.py <путь_к_файлу>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    fix_indentation(file_path) 