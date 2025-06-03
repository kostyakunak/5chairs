#!/usr/bin/env python3

import sys

def fix_keyboard_builders(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Исправляем первый builder в функции confirm_create_meeting
    for i, line in enumerate(lines):
        if "# Создаем клавиатуру для дальнейших действий" in line and i+1 < len(lines) and "builder = InlineKeyboardBuilder()" in lines[i+1]:
            if lines[i+1].startswith("    builder"):
                # Отступ уже правильный
                continue
            
            # Исправляем отступ
            lines[i+1] = "        builder = InlineKeyboardBuilder()\n"
            print(f"Исправлен отступ для builder в строке {i+1}")
    
    # Исправляем второй builder в функции confirm_add_user_to_meeting
    for i, line in enumerate(lines):
        if "# Создаем клавиатуру для дальнейших действий" in line and i+1 < len(lines) and "builder = InlineKeyboardBuilder()" in lines[i+1]:
            if i > 1000:  # Примерное положение второго builder
                if lines[i+1].startswith("    builder"):
                    # Отступ уже правильный
                    continue
                
                # Исправляем отступ
                lines[i+1] = "        builder = InlineKeyboardBuilder()\n"
                print(f"Исправлен отступ для builder в строке {i+1}")
    
    # Записываем изменения обратно в файл
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print(f"Исправления внесены в файл {file_path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Использование: python fix_keyboard_builders.py <путь_к_файлу>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    fix_keyboard_builders(file_path) 