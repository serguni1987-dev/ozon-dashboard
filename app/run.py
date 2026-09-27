"""
run.py — утренний ритуал. Одна команда:
1. Проверяет downloads/ на новые .xlsx
2. parse_xlsx.py
3. sync_finance.py — начисления из API
4. fetch_current_prices.py — актуальные цены
5. fetch_current_stocks.py — актуальные остатки
6. sync_archived.py — только с флагом --archive
7. sync_decisions.py — решения из Google Sheets
8. sheets_sync.py — выгрузка в Google Sheets
9. daily_dashboard.py — локальный пульт
10. decision_effects.py — дневник
11. backup_db.py — копия базы

Использование:
  py run.py              # быстрый запуск
  py run.py --archive    # + синхронизация архива
  py run.py --no-effects # без дневника решений
"""
import os
import sys
import glob
import sqlite3
import subprocess
from datetime import datetime

DB_PATH = "ozon.db"
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.dirname(_APP_DIR)
DOWNLOADS_DIR = os.path.join(_ROOT_DIR, "downloads")
PY = sys.executable


def already_ingested(file_name):
    if not os.path.exists(DB_PATH):
        return False
    con = sqlite3.connect(DB_PATH)
    try:
        row = con.execute(
            "SELECT 1 FROM ingest_log WHERE file_name = ? LIMIT 1",
            (file_name,),
        ).fetchone()
        return row is not None
    finally:
        con.close()


def list_new_files():
    if not os.path.isdir(DOWNLOADS_DIR):
        return []
    files = glob.glob(os.path.join(DOWNLOADS_DIR, "*.xlsx"))
    return [f for f in files if not already_ingested(os.path.basename(f))]


def run(cmd, stop_on_error=True):
    print(f"\n>>> {' '.join(cmd)}")
    r = subprocess.run(cmd)
    if r.returncode != 0 and stop_on_error:
        print(f"\n[ERROR] команда вернула код {r.returncode}")
        sys.exit(r.returncode)
    return r.returncode


def main():
    do_archive = "--archive" in sys.argv
    skip_effects = "--no-effects" in sys.argv
    skip_dashboard = "--no-dashboard" in sys.argv

    print("=" * 100)
    print(f"УТРЕННИЙ РИТУАЛ  |  {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print("=" * 100)

    # 1-2. Новые .xlsx
    new_files = list_new_files()
    if new_files:
        print(f"\n[1] Найдено новых .xlsx: {len(new_files)}")
        for f in new_files:
            print(f"    • {os.path.basename(f)}")
        print(f"\n[2] Обрабатываю каждый по очереди...")
        for f in new_files:
            fname = os.path.basename(f)
            print(f"\n    --- {fname} ---")
            run([PY, "parse_xlsx.py", f"--file={fname}"], stop_on_error=False)
    else:
        print("\n[1] Новых .xlsx нет. Использую текущие данные.")

    # 2.5. Отчёт о реализации за прошлый месяц (с защитой от перезаписи)
    print("\n[2.5] Отчёт о реализации за прошлый месяц...")
    run([PY, "sync_monthly.py"], stop_on_error=False)

    # 3. Финансы из API
    print("\n[3] Синхронизация финансов из Ozon API...")
    run([PY, "sync_finance.py"], stop_on_error=False)

    # 3.5. Проверка новых type_id (алерт, не блокирует)
    print("\n[3.5] Проверка новых type_id...")
    run([PY, "PNL\\_diag\\check_all_types.py"], stop_on_error=False)

    # 3.6. P&L — сборка и выгрузка в Google Sheets
    print("\n[3.6] Сборка P&L в Google Sheets...")
    run([PY, "PNL\\sync_pnl.py", "2026"], stop_on_error=False)
    run([PY, "PNL\\pnl_format.py"], stop_on_error=False)
    run([PY, "PNL\\fix_sheet_full.py"], stop_on_error=False)

    # 4. Актуальные цены
    print("\n[4] Актуальные цены из Ozon API...")
    run([PY, "fetch_current_prices.py"], stop_on_error=False)

    # 5. Актуальные остатки
    print("\n[5] Актуальные остатки из Ozon API...")
    run([PY, "fetch_current_stocks.py"], stop_on_error=False)

    # 6. Архив — только с флагом
    if do_archive:
        print("\n[6] Синхронизация архива...")
        run([PY, "sync_archived.py"], stop_on_error=False)
    else:
        print("\n[6] Архив не синхронизирую (используй --archive раз в неделю)")

    # 7. Помечаем свои/чужие (SKU из отчёта реализации → is_own=1)
    print("\n[7] Помечаю свои SKU...")
    run([PY, "mark_brands.py"], stop_on_error=False)

    # 8. Контроль себестоимости (алерт, не блокирующий)
    print("\n[8] Проверка себестоимости...")
    run([PY, "check_costs_alert.py"], stop_on_error=False)

    # 9. Решения из Google Sheets
    print("\n[9] Синхронизация решений из Google Sheets...")
    run([PY, "sync_decisions.py"], stop_on_error=False)

    # 10. Google Sheets
    print("\n[10] Выгружаю в Google Sheets...")
    run([PY, "sheets_sync.py"], stop_on_error=False)

    # 11. Локальный пульт (пропускается при --no-dashboard)
    if skip_dashboard:
        print("\n[11] Пульт не открываю (--no-dashboard)")
    else:
        print("\n[11] Открываю пульт...")
        run([PY, "daily_dashboard.py"])

    # 12. Дневник решений
    if not skip_effects:
        print("\n[12] Дневник решений...")
        run([PY, "decision_effects.py"], stop_on_error=False)

    # 11. Резервная копия
    print("\n[11] Резервная копия базы...")
    run([PY, "backup_db.py"], stop_on_error=False)


if __name__ == "__main__":
    main()
