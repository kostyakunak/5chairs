#!/usr/bin/env python3

import sys

def fix_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Находим проблемные строки
    start_line = 0
    for i, line in enumerate(lines):
        if "# Add user to meeting" in line:
            start_line = i
            break
    
    if start_line > 0:
        # Заменяем проблемный блок
        corrected_lines = [
            "    # Add user to meeting\n",
            "    try:\n",
            "        await add_meeting_member(meeting_id, application['user_id'])\n",
            "        logger.info(f\"[approve_and_add_to_meeting] Пользователь user_id={application['user_id']} добавлен в встречу meeting_id={meeting_id}\")\n",
            "    except Exception as e:\n",
            "        logger.error(f\"[approve_and_add_to_meeting] Ошибка при добавлении пользователя user_id={application['user_id']} в встречу meeting_id={meeting_id}: {e}\")\n",
            "        await callback.message.edit_text(f\"Error adding user to meeting: {e}\")\n",
            "        await state.clear()\n",
            "        return\n"
        ]
        
        # Заменяем строки
        lines[start_line:start_line+9] = corrected_lines
        
        # Записываем изменения обратно в файл
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        
        print(f"Исправлены отступы в блоке try-except в файле {file_path}")
    else:
        print("Проблемный блок не найден")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Использование: python fix_applications.py <путь_к_файлу>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    fix_file(file_path) 