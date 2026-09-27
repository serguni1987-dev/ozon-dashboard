"""patch_run: добавить P&L в run.py после sync_monthly."""
import shutil
from datetime import datetime

SRC = "run.py"
bak = f"{SRC}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
shutil.copy(SRC, bak)
print(f"Бэкап: {bak}")

src = open(SRC, encoding="utf-8").read()

old = '''    # 2.5. Отчёт о реализации за прошлый месяц (с защитой от перезаписи)
    print("\\n[2.5] Отчёт о реализации за прошлый месяц...")
    run([PY, "sync_monthly.py"], stop_on_error=False)

    # 3. Финансы из API'''

new = '''    # 2.5. Отчёт о реализации за прошлый месяц (с защитой от перезаписи)
    print("\\n[2.5] Отчёт о реализации за прошлый месяц...")
    run([PY, "sync_monthly.py"], stop_on_error=False)

    # 2.6. P&L — синк в Google Sheets
    print("\\n[2.6] Сборка P&L в Google Sheets...")
    run([PY, "PNL\\\\sync_pnl.py", "2026"], stop_on_error=False)
    run([PY, "PNL\\\\pnl_format.py"], stop_on_error=False)
    run([PY, "PNL\\\\fix_sheet_full.py"], stop_on_error=False)

    # 3. Финансы из API'''

if old in src:
    src = src.replace(old, new)
    print("[OK] P&L добавлен в run.py")
else:
    print("[?] НЕ найден блок sync_monthly")
    # найти как выглядит
    for i, line in enumerate(src.splitlines(), 1):
        if "sync_monthly" in line:
            print(f"    {i}: {line}")

open(SRC, "w", encoding="utf-8").write(src)
print()
