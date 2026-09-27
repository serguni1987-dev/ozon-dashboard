import sqlite3
c = sqlite3.connect("ozon.db")
c.row_factory = sqlite3.Row

month = "2026-04"
d1, d2 = "2026-04-01", "2026-05-01"

def to_f(v):
    try: return float(v or 0)
    except: return 0.0

# real_skus
real = [r[0] for r in c.execute(
    "SELECT DISTINCT sku FROM monthly_realization_rows WHERE month = ?", (month,)
)]
print(f"real_skus: {len(real)}")
print()

# Себестоимость по SKU
def get_cost(sku):
    r = c.execute("""
        SELECT cost_price FROM product_cost_history
        WHERE sku = ? AND date_from < ?
        ORDER BY date_from DESC LIMIT 1
    """, (sku, d2)).fetchone()
    return to_f(r[0]) if r else 0

# ── Вариант 1: текущий fallback (seller_price IS NOT NULL) ──
v1 = 0
for sku in real:
    cost = get_cost(sku)
    if cost == 0: continue
    r = c.execute("""
        SELECT SUM(sign) AS units FROM (
            SELECT DISTINCT unit_number,
                   CASE WHEN seller_price > 0 THEN 1
                        WHEN seller_price < 0 THEN -1 ELSE 0 END AS sign
            FROM accruals
            WHERE sku = ? AND date >= ? AND date < ?
              AND accrued_category = 'POSTING' AND seller_price IS NOT NULL
        )
    """, (sku, d1, d2)).fetchone()
    units = int(r[0] or 0) if r else 0
    if units != 0:
        v1 += cost * units

# ── Вариант 2: + POSTING с seller_price IS NULL, total_amount > 0 ──
v2 = v1  # начинаем с v1
for sku in real:
    cost = get_cost(sku)
    if cost == 0: continue
    r = c.execute("""
        SELECT COUNT(DISTINCT unit_number) AS units
        FROM accruals
        WHERE sku = ? AND date >= ? AND date < ?
          AND accrued_category = 'POSTING'
          AND seller_price IS NULL AND total_amount > 0
    """, (sku, d1, d2)).fetchone()
    units = int(r[0] or 0) if r else 0
    if units > 0:
        v2 += cost * units

# ── Вариант 3: + POSTING с seller_price IS NULL, total_amount < 0 ──
v3 = v2
for sku in real:
    cost = get_cost(sku)
    if cost == 0: continue
    r = c.execute("""
        SELECT COUNT(DISTINCT unit_number) AS units
        FROM accruals
        WHERE sku = ? AND date >= ? AND date < ?
          AND accrued_category = 'POSTING'
          AND seller_price IS NULL AND total_amount < 0
    """, (sku, d1, d2)).fetchone()
    units = int(r[0] or 0) if r else 0
    if units > 0:
        v3 -= cost * units

# ── Вариант 4: всё, включая seller_price IS NULL без фильтра total_amount ──
v4 = 0
for sku in real:
    cost = get_cost(sku)
    if cost == 0: continue
    r = c.execute("""
        SELECT COUNT(DISTINCT unit_number) AS units
        FROM accruals
        WHERE sku = ? AND date >= ? AND date < ?
          AND accrued_category = 'POSTING'
    """, (sku, d1, d2)).fetchone()
    units = int(r[0] or 0) if r else 0
    v4 += cost * units

print(f"Ozon эталон:                             28 084")
print(f"Вариант 1 (текущий, seller_price IS NOT NULL): {v1:>10,.0f}  Δ={v1-28084:>+8,.0f}")
print(f"Вариант 2 (+ null, total_amount > 0):     {v2:>10,.0f}  Δ={v2-28084:>+8,.0f}")
print(f"Вариант 3 (+ null, total_amount < 0):     {v3:>10,.0f}  Δ={v3-28084:>+8,.0f}")
print(f"Вариант 4 (все POSTING):                  {v4:>10,.0f}  Δ={v4-28084:>+8,.0f}")

c.close()