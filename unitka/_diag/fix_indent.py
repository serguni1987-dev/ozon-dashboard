from pathlib import Path

path = Path(r"C:\Users\sergu\Desktop\проект\unitka\web_app.py")
content = path.read_text(encoding="utf-8")
lines = content.splitlines()

fixed = False
for i, line in enumerate(lines):
    # Ищем нашу строку независимо от того, сколько пробелов в начале
    if 'schema = "Таблицы: " + chr(10)' in line:
        # Принудительно ставим 4 пробела (один уровень вложенности)
        lines[i] = '    schema = "Таблицы: " + chr(10)'
        fixed = True
        break

if fixed:
    path.write_text("\n".join(lines), encoding="utf-8")
    print("УСПЕХ: Отступы исправлены!")
else:
    print("ОШИБКА: Не нашел строку schema.")