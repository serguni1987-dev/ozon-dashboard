"""
check_sheets_env.py — проверяем готовность окружения для Google Sheets.
"""
import os
import glob

APP_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(APP_DIR)

print("=" * 80)
print("ПРОВЕРКА ОКРУЖЕНИЯ GOOGLE SHEETS")
print("=" * 80)

# 1. credentials.json
cred_paths = [
    os.path.join(APP_DIR, "credentials.json"),
    os.path.join(ROOT, "credentials.json"),
    "credentials.json",
]
print("\n[1] credentials.json:")
found_cred = None
for p in cred_paths:
    if os.path.exists(p):
        size = os.path.getsize(p)
        print(f"    ✅ {p} ({size} байт)")
        found_cred = p
        break
    else:
        print(f"    — {p}")

# 2. sheets_sync.py
print("\n[2] sheets_sync.py:")
sync_paths = [
    os.path.join(APP_DIR, "sheets_sync.py"),
    os.path.join(ROOT, "sheets_sync.py"),
]
found_sync = None
for p in sync_paths:
    if os.path.exists(p):
        size = os.path.getsize(p)
        print(f"    ✅ {p} ({size} байт)")
        found_sync = p
    else:
        print(f"    — {p}")

# 3. gspread
print("\n[3] Библиотеки:")
try:
    import gspread
    print(f"    ✅ gspread {gspread.__version__}")
except ImportError:
    print(f"    ❌ gspread не установлен")
    print(f"       py -m pip install gspread google-auth gspread-formatting")

try:
    import gspread_formatting
    print(f"    ✅ gspread_formatting")
except ImportError:
    print(f"    ❌ gspread_formatting не установлен")

# 4. Список файлов в app/
print("\n[4] Файлы в app/:")
files = sorted(os.listdir(APP_DIR))
for f in files:
    if f.startswith(("sync_", "calc_", "fetch_", "diag_", "patch_", "fix_", "clear_")):
        continue
    if f.endswith(".py"):
        print(f"    {f}")

# 5. Есть ли вообще Google Sheets настройка
print("\n[5] Вывод:")
if found_cred and found_sync:
    print("    ✅ Всё готово — можно делать лист ФАКТ")
elif found_cred:
    print("    ⚠️ credentials.json есть, но sheets_sync.py отсутствует")
    print("       → нужно скопировать sheets_sync.py из старого проекта")
elif found_sync:
    print("    ⚠️ sheets_sync.py есть, но нет credentials.json")
    print("       → нужно скопировать credentials.json из старого проекта")
else:
    print("    ❌ Ни credentials.json, ни sheets_sync.py не найдены")
    print("       → этот ПК — не тот, где настраивался Google Sheets")
    print("       → можно сделать лист ФАКТ локально (CSV)")
