"""fix_is_own.py — проставляет is_own=1 всем SKU из monthly_realization_rows.
Плюс — для 3 новых SKU с brand=None проставляет бренд VIVA.
"""
import sqlite3

c = sqlite3.connect("ozon.db")
c.row_factory = sqlite3.Row

# ── 1. is_own=1 для всех SKU из реализации ──
print("=== Проставляю is_own=1 для SKU из monthly_realization_rows ===")
before = c.execute("SELECT COUNT(*) FROM products WHERE is_own=1").fetchone()[0]
print(f"  Было с is_own=1: {before}")

c.execute("""
    UPDATE products
    SET is_own = 1
    WHERE sku IN (
        SELECT DISTINCT sku FROM monthly_realization_rows
        WHERE sku IS NOT NULL
    )
""")
c.commit()

after = c.execute("SELECT COUNT(*) FROM products WHERE is_own=1").fetchone()[0]
print(f"  Стало с is_own=1: {after}  (+{after-before})")

# ── 2. Бренд для 3 SKU без бренда ──
print()
print("=== Проставляю brand='VIVA - HOME TEXTILE' там, где None и is_own=1 ===")
c.execute("""
    UPDATE products
    SET brand = 'VIVA - HOME TEXTILE'
    WHERE brand IS NULL AND is_own = 1
""")
c.commit()

n = c.execute("SELECT COUNT(*) FROM products WHERE brand='VIVA - HOME TEXTILE' AND is_own=1").fetchone()[0]
print(f"  Всего с брендом VIVA: {n}")

# ── 3. Проверка ──
print()
print("=== Контрольная проверка: 16 SKU ===")
targets = (1879636339, 1281819166, 2288681486, 1591552350, 1609915178,
           2288693078, 1281720312, 1879635959, 1879635938, 1598572996,
           1879636428, 1267412652, 1616350111, 1331069847, 1610041376, 1609915213)
q = ",".join(map(str, targets))
for r in c.execute(f"""
    SELECT sku, offer_id, brand, is_own, cost_price
    FROM products WHERE sku IN ({q})
    ORDER BY sku
"""):
    print(f"  sku={r['sku']:>12}  is_own={r['is_own']}  cost={r['cost_price']}  "
          f"brand={r['brand']!r}")

c.close()
print()
print("[OK] Готово")