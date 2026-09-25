"""
check_costs_file.py - что в costs_all.csv и каких SKU не хватает.
"""
import csv
import sqlite3
import os

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(APP_DIR, "ozon.db")
CSV = "costs_all.csv"

if not os.path.exists(CSV):
    print(f"[ERROR] Файл {CSV} не найден")
    raise SystemExit

# Читаем CSV
with open(CSV, encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f, delimiter=";")
    rows = list(reader)

print("=" * 80)
print(f"ФАЙЛ {CSV}")
print("=" * 80)
print(f"\nСтрок: {len(rows)}")
print(f"Колонки: {list(rows[0].keys())}")

# Какие offer_id в файле
file_offers = {}
for r in rows:
    oid = (r.get("offer_id") or "").strip()
    cost = (r.get("cost_price") or "").strip()
    if oid:
        file_offers[oid] = cost

filled = sum(1 for c in file_offers.values() if c and c != "0")
print(f"\nУникальных offer_id: {len(file_offers)}")
print(f"С заполненной себестоимостью: {filled}")
print(f"Без себестоимости: {len(file_offers) - filled}")

# Какие offer_id в БД (все свои)
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

db_offers = [r[0] for r in con.execute("""
    SELECT offer_id FROM products
    WHERE is_own = 1 AND offer_id IS NOT NULL AND offer_id != ''
""")]
print(f"\nСвоих offer_id в БД: {len(db_offers)}")

# Которых нет в файле
missing = [oid for oid in db_offers if oid not in file_offers]
print(f"\nНЕТ в файле: {len(missing)}")
for oid in missing[:30]:
    row = con.execute(
        "SELECT name, cost_price FROM products WHERE offer_id = ?", (oid,)
    ).fetchone()
    name = (row["name"] or "")[:60] if row else ""
    cost = row["cost_price"] if row else None
    print(f"  {oid:<25} cost={cost}  {name}")

if len(missing) > 30:
    print(f"  ... и ещё {len(missing) - 30}")

# Какие SKU в realization за янв-авг, которых нет в файле
print(f"\n" + "=" * 80)
print("SKU ИЗ REALIZATION (янв-авг), КОТОРЫХ НЕТ В ФАЙЛЕ:")
print("=" * 80)

real_skus = [r[0] for r in con.execute("""
    SELECT DISTINCT r.sku, p.offer_id
    FROM monthly_realization_rows r
    LEFT JOIN products p ON p.sku = r.sku
    WHERE r.month < '2026-09'
""")]

missing_real = []
for r in con.execute("""
    SELECT DISTINCT r.sku, p.offer_id, p.name
    FROM monthly_realization_rows r
    LEFT JOIN products p ON p.sku = r.sku
    WHERE r.month < '2026-09'
"""):
    if r["offer_id"] and r["offer_id"] not in file_offers:
        missing_real.append(r)

print(f"\nНайдено: {len(missing_real)}")
for r in missing_real[:30]:
    name = (r["name"] or "")[:50]
    print(f"  {r['sku']:<15} {r['offer_id']:<25} {name}")

con.close()
