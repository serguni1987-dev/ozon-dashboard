"""patch_run_order: P&L после sync_finance + проверка type_id."""
import shutil
from datetime import datetime

SRC = "run.py"
bak = f"{SRC}.bak-order-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
shutil.copy(SRC, bak)
print(f"Бэкап: {bak}")

src = open(SRC, encoding="utf-8").read()

# ── 1. Удалить текущий блок [2.6] P&L (он стоит между 2.5 и 3) ──
old_pnl = '''    # 2.6. P&L — синк в Google Sheets
    print("\\n[2.6] Сборка P&L в Google Sheets...")
    run([PY, "PNL\\\\sync_pnl.py", "2026"], stop_on_error=False)
    run([PY, "PNL\\\\pnl_format.py"], stop_on_error=False)
    run([PY, "PNL\\\\fix_sheet_full.py"], stop_on_error=False)

    # 3. Финансы из API'''

new_step3 = '''    # 3. Финансы из API'''

if old_pnl in src:
    src = src.replace(old_pnl, new_step3)
    print("[OK] старый блок P&L (2.6) удалён")
else:
    print("[?] не найден старый блок P&L")

# ── 2. Вставить блок P&L + проверку type_id ПОСЛЕ sync_finance ──
old_fin = '''    # 3. Финансы из API
    print("\\n[3] Синхронизация финансов из Ozon API...")
    run([PY, "sync_finance.py"], stop_on_error=False)

    # 4. Актуальные цены'''

new_fin = '''    # 3. Финансы из API
    print("\\n[3] Синхронизация финансов из Ozon API...")
    run([PY, "sync_finance.py"], stop_on_error=False)

    # 3.5. Проверка новых type_id (алерт, не блокирует)
    print("\\n[3.5] Проверка новых type_id...")
    run([PY, "PNL\\\\_diag\\\\check_all_types.py"], stop_on_error=False)

    # 3.6. P&L — сборка и выгрузка в Google Sheets
    print("\\n[3.6] Сборка P&L в Google Sheets...")
    run([PY, "PNL\\\\sync_pnl.py", "2026"], stop_on_error=False)
    run([PY, "PNL\\\\pnl_format.py"], stop_on_error=False)
    run([PY, "PNL\\\\fix_sheet_full.py"], stop_on_error=False)

    # 4. Актуальные цены'''

if old_fin in src:
    src = src.replace(old_fin, new_fin)
    print("[OK] P&L перенесён после sync_finance + добавлена проверка type_id")
else:
    print("[?] не найден блок sync_finance")

open(SRC, "w", encoding="utf-8").write(src)
print()
