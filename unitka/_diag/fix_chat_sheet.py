from pathlib import Path

path = Path(r"C:\Users\sergu\Desktop\проект\unitka\chat_in_sheets.py")
content = path.read_text(encoding="utf-8")

old_code = '''    try:
        ws = sh.worksheet(CHAT_SHEET)
    except gspread.WorksheetNotFound:
        print(f"Ошибка: Лист '{CHAT_SHEET}' не найден. Создайте его.")
        return'''

new_code = '''    try:
        ws = sh.worksheet(CHAT_SHEET)
    except gspread.WorksheetNotFound:
        print(f"Лист '{CHAT_SHEET}' не найден. Создаю новый...")
        ws = sh.add_worksheet(title=CHAT_SHEET, rows=20, cols=2)
        ws.update('A1', 'Вопрос')
        ws.update('B1', 'Ответ ИИ')
        print("Лист создан! Начинаю слушать.")'''

if old_code in content:
    content = content.replace(old_code, new_code)
    path.write_text(content, encoding="utf-8")
    print("УСПЕХ: Скрипт теперь сам создает лист 'Чат с ИИ'")
else:
    print("ОШИБКА: Не нашел старый код. Возможно, файл изменился.")