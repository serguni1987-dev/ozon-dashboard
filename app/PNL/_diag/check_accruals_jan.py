import sqlite3
c = sqlite3.connect("ozon.db")
c.row_factory = sqlite3.Row

print("=== Колонки accruals ===")
print(" ", [r[1] for r in c.execute("PRAGMA table_info(accruals)")])

print("\n=== accruals за январь: что есть ===")
r = c.execute("""
    SELECT
        COUNT(*) AS total,
        SUM(CASE WHEN accrued_category = 'POSTING' THEN 1 ELSE 0 END) AS posting,
        SUM(CASE WHEN accrued_category = 'POSTING' AND seller_price IS NOT NULL THEN 1 ELSE 0 END) AS posting_sp,
        SUM(CASE WHEN accrued_category = 'POSTING' AND sku IS NOT NULL THEN 1 ELSE 0 END) AS posting_sku,
        SUM(CASE WHEN accrued_category = 'POSTING' AND unit_number IS NOT NULL THEN 1 ELSE 0 END) AS posting_unit
    FROM accruals
    WHERE date >= '2026-01-01' AND date < '2026-02-01'
""").fetchone()
for k, v in zip(r.keys(), r):
    print(f"  {k}: {v}")

print("\n=== Уникальные accrued_category за январь ===")
for r in c.execute("""
    SELECT accrued_category, COUNT(*) AS n
    FROM accruals
    WHERE date >= '2026-01-01' AND date < '2026-02-01'
    GROUP BY accrued_category ORDER BY n DESC
"""):
    print(f"  {r['accrued_category']}: {r['n']}")

print("\n=== Пример POSTING за январь (5 шт) ===")
for r in c.execute("""
    SELECT sku, unit_number, seller_price, accrued_category
    FROM accruals
    WHERE date >= '2026-01-01' AND date < '2026-02-01'
      AND accrued_category = 'POSTING'
      AND sku IS NOT NULL
    LIMIT 5
"""):
    print(f"  sku={r['sku']}  unit={r['unit_number']}  sp={r['seller_price']}")

c.close()