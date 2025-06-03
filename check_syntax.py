#!/usr/bin/env python3

import py_compile
import sys

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Использование: python check_syntax.py <путь_к_файлу>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    try:
        py_compile.compile(file_path, doraise=True)
        print(f"Компиляция {file_path} успешна! Файл не содержит синтаксических ошибок.")
    except py_compile.PyCompileError as e:
        print(f"Ошибка компиляции в файле {file_path}:")
        print(str(e))
        sys.exit(1) 