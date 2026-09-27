import sqlite3
c = sqlite3.connect("ozon.db")
c.row_factory = sqlite3.Row

month = "2026-04"
d1, d2 = "2026-04-01", "2026-05-01"
OZON = 28084

def to_f(v):
    try: return float(v or 0)
    except: return 0.0

def get_cost(sku):
    r = c.execute("""
        SELECT cost_price FROM product_cost_history
        WHERE sku = ? AND date_from < ?
        ORDER BY date_from DESC LIMIT 1
    """, (sku, d2)).fetchone()
    return to_f(r[0]) if r else 0

# Сколько SKU где есть
real_skus = [r[0] for r in c.execute(
    "SELECT DISTINCT sku FROM monthly_realization_rows WHERE month = ?", (month,))]
sales_skus = [r[0] for r in c.execute("""
    SELECT DISTINCT sku FROM sales_daily WHERE date >= ? AND date < ?
    AND (orders_units > 0 OR delivered > 0)
""", (d1, d2))]
accruals_skus = [r[0] for r in c.execute("""
    SELECT DISTINCT sku FROM accruals WHERE date >= ? AND date < ?
    AND accrued_category = 'POSTING' AND sku IS NOT NULL
""", (d1, d2))]

print(f"SKU в monthly_realization_rows:  {len(real_skus)}")
print(f"SKU в sales_daily (orders>0):    {len(sales_skus)}")
print(f"SKU в accruals POSTING:          {len(accruals_skus)}")
print()

# ── Вариант A: cost × orders_units из sales_daily ──
va = 0
for sku in real_skus:
    cost = get_cost(sku)
    if cost == 0: continue
    r = c.execute("""
        SELECT SUM(orders_units) AS u FROM sales_daily
        WHERE sku = ? AND date >= ? AND date < ?
    """, (sku, d1, d2)).fetchone()
    units = int(r[0] or 0) if r else 0
    if units > 0:
        va += cost * units

# ── Вариант B: cost × COUNT(DISTINCT unit) из POSTING без фильтров ──
vb = 0
for sku in real_skus:
    cost = get_cost(sku)
    if cost == 0: continue
    r = c.execute("""
        SELECT COUNT(DISTINCT unit_number) AS u FROM accruals
        WHERE sku = ? AND date >= ? AND date < ? AND accrued_category = 'POSTING'
    """, (sku, d1, d2)).fetchone()
    units = int(r[0] or 0) if r else 0
    if units > 0:
        vb += cost * units

# ── Вариант C: cost × COUNT(unit) из ITEM без фильтров ──
vc = 0
for sku in real_skus:
    cost = get_cost(sku)
    if cost == 0: continue
    r = c.execute("""
        SELECT COUNT(DISTINCT unit_number) AS u FROM accruals
        WHERE sku = ? AND date >= ? AND date < ? AND accrued_category = 'ITEM'
    """, (sku, d1, d2)).fetchone()
    units = int(r[0] or 0) if r else 0
    if units > 0:
        vc += cost * units

# ── Вариант D: cost × quantity из monthly_realization_rows (без is_return) ──
vd = 0
for sku in real_skus:
    cost = get_cost(sku)
    if cost == 0: continue
    r = c.execute("""
        SELECT SUM(quantity) AS q FROM monthly_realization_rows
        WHERE sku = ? AND month = ?
    """, (sku, month)).fetchone()
    q = int(r[0] or 0) if r else 0
    if q != 0:
        vd += cost * q

# ── Вариант E: cost × quantity × 2 (если где-то двойной счёт) ──
ve = vd * 2

print(f"Ozon эталон:                          {OZON:>10,.0f}")
print(f"A (orders_units):                     {va:>10,.0f}  Δ={va-OZON:>+8,.0f}")
print(f"B (COUNT POSTING без фильтра):        {vb:>10,.0f}  Δ={vb-OZON:>+8,.0f}")
print(f"C (COUNT ITEM):                       {vc:>10,.0f}  Δ={vc-OZON:>+8,.0f}")
print(f"D (quantity из realization):          {vd:>10,.0f}  Δ={vd-OZON:>+8,.0f}")
print(f"E (D × 2):                            {ve:>10,.0f}  Δ={ve-OZON:>+8,.0f}")
print()

# ── Разбивка по SKU: cost × quantity ──
print("── Наша разбивка (cost × quantity realization) ──")
total_d = 0
for sku in real_skus:
    cost = get_cost(sku)
    r = c.execute("""
        SELECT SUM(quantity) AS q FROM monthly_realization_rows
        WHERE sku = ? AND month = ?
    """, (sku, month)).fetchone()
    q = int(r[0] or 0) if r else 0
    if q and cost:
        total_d += cost * q
        print(f"  sku={sku:>12}  cost={cost:>8.0f}  qty={q:>3}  = {cost*q:>10,.0f}")

print(f"\nИтого: {total_d:,.0f}")

c.close()