from pathlib import Path

path = Path(r"C:\Users\sergu\Desktop\проект\unitka\web_app.py")
if not path.exists():
    print("Файл не найден!")
else:
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()
    
    fixed = False
    for i, line in enumerate(lines):
        # Ищем сломанную строку
        if 'schema = "Таблицы:' in line:
            # Заменяем на правильную, используя chr(10) для переноса строки
            lines[i] = '        schema = "Таблицы: " + chr(10)'
            # Если следующая строка - это просто висящая кавычка, удаляем её
            if i + 1 < len(lines) and lines[i+1].strip() == '"':
                lines.pop(i + 1)
            fixed = True
            break
            
    if fixed:
        path.write_text("\n".join(lines), encoding="utf-8")
        print("УСПЕХ: Ошибка в web_app.py успешно исправлена!")
    else:
        print("Сломанная строка не найдена (возможно, уже исправлена).")