from pathlib import Path
import re

path = Path(r"C:\Users\sergu\Desktop\проект\unitka\web_app.py")
content = path.read_text(encoding="utf-8")

new_prompt = '''    system_prompt = f"""Ты — SQL-робот для базы SQLite. Сейчас 2026 год.
СХЕМА БАЗЫ: {schema}

ПРАВИЛА:
1. Пиши ТОЛЬКО SQL-запрос. Никакого текста, начиная со слова SELECT.
2. Для выручки по месяцам: SELECT period as date, revenue FROM monthly_reports ORDER BY period
3. Для убыточных товаров: SELECT sku, profit FROM abc_xyz WHERE profit < 0 ORDER BY profit ASC LIMIT 3
4. Всегда фильтруй по 2026 году (WHERE date LIKE '2026-%').
"""'''

# Ищем блок с system_prompt и заменяем его целиком
pattern = re.compile(r'system_prompt = f""".*?"""', re.DOTALL)
if pattern.search(content):
    content = pattern.sub(new_prompt.strip(), content)
    path.write_text(content, encoding="utf-8")
    print("УСПЕХ: Промпт обновлен (7B теперь знает про 2026 год и таблицу abc_xyz)")
else:
    print("ОШИБКА: Не удалось найти system_prompt в web_app.py")