"""fix_duplicate: убрать задвоенную строку skip_dashboard."""
import shutil
from datetime import datetime

SRC = "run.py"
bak = f"{SRC}.bak-dup-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
shutil.copy(SRC, bak)
print(f"Бэкап: {bak}")

src = open(SRC, encoding="utf-8").read()

# Заменяем две подряд идущие одинаковые строки на одну
old = '''    skip_dashboard = "--no-dashboard" in sys.argv
    skip_dashboard = "--no-dashboard" in sys.argv'''
new = '''    skip_dashboard = "--no-dashboard" in sys.argv'''

if old in src:
    src = src.replace(old, new)
    open(SRC, "w", encoding="utf-8").write(src)
    print("[OK] дубликат убран")
else:
    print("[?] не найден дубликат")

# Проверка
import re
count = len(re.findall(r'skip_dashboard = ', src))
print(f"Теперь объявлений skip_dashboard: {count}")
