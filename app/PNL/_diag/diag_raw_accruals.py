"""
diag_raw_accruals.py — смотрим сырой JSON, ищем скрытые услуги.
"""
import os
import json
import sqlite3

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(APP_DIR, "ozon.db")

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

# Все поля из raw_json одного accrual
r = con.execute("""
    SELECT raw_json FROM accruals
    WHERE date >= '2026-08-01' AND date < '2026-09-01'
      AND total_amount < 0
    LIMIT 1
""").fetchone()

if not r:
    print("Нет данных за август")
    con.close()
    raise SystemExit

data = json.loads(r["raw_json"])

print("=" * 80)
print("СТРУКТУРА ACCRUAL (сырая)")
print("=" * 80)
print(json.dumps(data, ensure_ascii=False, indent=2)[:4000])

# Ищем все блоки, которые содержат услуги
print("\n\n" + "=" * 80)
print("ПОИСК БЛОКОВ С УСЛУГАМИ")
print("=" * 80)

for key in ["item_fees", "non_item_fee", "container_fees",
            "posting", "services", "products"]:
    if key in data:
        val = data[key]
        if val:
            print(f"\n[{key}]")
            print(json.dumps(val, ensure_ascii=False, indent=2)[:2000])

# Проверяем — есть ли строки в accruals, у которых нет записей в accruals_services
print("\n\n" + "=" * 80)
print("ACCRUALS БЕЗ SERVICES")
print("=" * 80)

rows = con.execute("""
    SELECT a.accrual_id, a.date, a.total_amount,
           (SELECT COUNT(*) FROM accruals_services s WHERE s.accrual_id = a.accrual_id) AS n_services
    FROM accruals a
    WHERE a.date >= '2026-08-01' AND a.date < '2026-09-01'
      AND (SELECT COUNT(*) FROM accruals_services s WHERE s.accrual_id = a.accrual_id) = 0
""").fetchall()

print(f"\nНайдено: {len(rows)}")
for r in rows[:20]:
    print(f"  accrual_id={r['accrual_id']}  date={r['date']}  total={r['total_amount']:.2f}")

con.close()
