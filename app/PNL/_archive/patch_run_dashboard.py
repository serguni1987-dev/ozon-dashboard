"""patch_run_dashboard: добавить --no-dashboard флаг."""
import shutil
from datetime import datetime

SRC = "run.py"
bak = f"{SRC}.bak-dash-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
shutil.copy(SRC, bak)
print(f"Бэкап: {bak}")

src = open(SRC, encoding="utf-8").read()

old1 = '''    do_archive = "--archive" in sys.argv
    skip_effects = "--no-effects" in sys.argv'''
new1 = '''    do_archive = "--archive" in sys.argv
    skip_effects = "--no-effects" in sys.argv
    skip_dashboard = "--no-dashboard" in sys.argv'''

if old1 in src:
    src = src.replace(old1, new1)
    print("[OK] флаг --no-dashboard добавлен")
else:
    print("[?] не найден блок разбора аргументов")

old2 = '''    # 11. Локальный пульт
    print("\\n[11] Открываю пульт...")
    run([PY, "daily_dashboard.py"])'''
new2 = '''    # 11. Локальный пульт (пропускается при --no-dashboard)
    if skip_dashboard:
        print("\\n[11] Пульт не открываю (--no-dashboard)")
    else:
        print("\\n[11] Открываю пульт...")
        run([PY, "daily_dashboard.py"])'''

if old2 in src:
    src = src.replace(old2, new2)
    print("[OK] шаг 11 обёрнут в условие")
else:
    print("[?] не найден блок daily_dashboard")

open(SRC, "w", encoding="utf-8").write(src)
print()
