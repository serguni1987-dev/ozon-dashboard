"""
diag_realization.py — смотрим реальную структуру ответа API.
"""
import sqlite3
import json

con = sqlite3.connect("ozon.db")
con.row_factory = sqlite3.Row

row = con.execute("""
    SELECT raw_json FROM monthly_realization_rows
    WHERE month = '2026-08' LIMIT 1
""").fetchone()

if not row:
    print("Нет данных. Запусти sync_monthly.py")
    con.close()
    raise SystemExit

data = json.loads(row["raw_json"])

print("=" * 80)
print("СТРУКТУРА ОДНОЙ СТРОКИ ОТЧЁТА")
print("=" * 80)
print()
print(json.dumps(data, ensure_ascii=False, indent=2))

con.close()
