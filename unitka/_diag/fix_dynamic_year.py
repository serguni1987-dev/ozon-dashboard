from pathlib import Path
import re

path = Path(r"C:\Users\sergu\Desktop\проект\unitka\web_app.py")
content = path.read_text(encoding="utf-8")

# 1. Добавляем импорт datetime, если его нет
if "import datetime" not in content:
    content = content.replace("import re", "import re\nimport datetime")

# 2. Делаем год динамическим в промпте
# Ищем текст "Сейчас 2026 год." и заменяем на динамический
content = re.sub(
    r'Сейчас 2026 год\.', 
    'Сейчас {datetime.datetime.now().year} год.', 
    content
)
# Если в промпте остался старый год в правилах, чистим
content = content.replace("Всегда фильтруй по 2026 году", "Всегда фильтруй по текущему году")

# 3. Меняем жесткий костыль на динамический
old_rule = '''sql_query = sql_query.replace("DATE_FORMAT", "strftime").replace("DATE(", "date(")
                # ЖЕСТКАЯ ЗАМЕНА ГОДА (чтобы модель не писала 2023)
                sql_query = sql_query.replace("2023", "2026").replace("2024", "2026").replace("2025", "2026")'''

new_rule = '''sql_query = sql_query.replace("DATE_FORMAT", "strftime").replace("DATE(", "date(")
                # ДИНАМИЧЕСКАЯ ЗАМЕНА ГОДА (заменяем любые старые года на текущий)
                current_year = str(datetime.datetime.now().year)
                sql_query = re.sub(r'20[0-2][0-5]', current_year, sql_query)'''

if old_rule in content:
    content = content.replace(old_rule, new_rule)
    path.write_text(content, encoding="utf-8")
    print("УСПЕХ: Год теперь динамический! В 2027 году система сама переключится.")
else:
    print("ОШИБКА: Не нашел блок с заменой года. Возможно, файл уже изменен.")