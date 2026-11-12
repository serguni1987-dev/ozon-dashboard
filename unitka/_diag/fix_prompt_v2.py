from pathlib import Path
import re

path = Path(r"C:\Users\sergu\Desktop\проект\unitka\web_app.py")
content = path.read_text(encoding="utf-8")

new_prompt = '''    system_prompt = f"""Ты — SQL-робот для базы SQLite.
СХЕМА БАЗЫ: {schema}

ПРАВИЛА:
1. Выдавай только SQL-запрос. Никакого текста, начиная со слова SELECT.
2. Для убыточных товаров используй таблицу abc_xyz. В ней НЕТ колонки date (только period). 
   Пример правильного запроса: SELECT sku, profit FROM abc_xyz WHERE profit < 0 ORDER BY profit ASC LIMIT 3
3. Для выручки по месяцам используй monthly_reports: SELECT period as date, revenue FROM monthly_reports ORDER BY period
4. Для выручки по дням используй realization_daily: SELECT date, SUM(sale_price) as revenue FROM realization_daily WHERE date LIKE '2026-%' GROUP BY date ORDER BY date
"""'''

pattern = re.compile(r'system_prompt = f""".*?"""', re.DOTALL)
if pattern.search(content):
    content = pattern.sub(new_prompt.strip(), content)
    path.write_text(content, encoding="utf-8")
    print("УСПЕХ: Промпт обновлен (добавлен правильный пример для abc_xyz)")
else:
    print("ОШИБКА: Не удалось найти system_prompt в web_app.py")