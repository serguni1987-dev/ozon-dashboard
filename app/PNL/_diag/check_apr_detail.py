import sqlite3
c = sqlite3.connect("ozon.db")
c.row_factory = sqlite3.Row
month = "2026-04"
d1, d2 = "2026-04-01", "2026-05-01"

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

print("═══ 1. real_skus из monthly_realization_rows ═══")
for r in c.execute("""
    SELECT sku, SUM(quantity) AS q, SUM(sale_price) AS slp
    FROM monthly_realization_rows WHERE month = ? GROUP BY sku
""", (month,)):
    cost = get_cost(r["sku"])
    print(f"  sku={r['sku']:>12}  qty={r['q']:>3}  slp={r['slp'] or 0:>10,.0f}  "
          f"cost={cost:>8.0f}  sum={cost * (r['q'] or 0):>10,.0f}")

print("\n═══ 2. Все unit POSTING за апрель ═══")
units = {}
for r in c.execute("""
    SELECT sku, unit_number, seller_price, total_amount
    FROM accruals WHERE date >= ? AND date < ? AND accrued_category = 'POSTING'
    ORDER BY sku, unit_number
""", (d1, d2)):
    key = (r["sku"], r["unit_number"])
    if key in units:
        units[key]["sp"] = units[key]["sp"] or r["seller_price"]
        units[key]["total"] += to_f(r["total_amount"])
        units[key]["n"] += 1
    else:
        units[key] = {
            "sku": r["sku"], "unit": r["unit_number"],
            "sp": r["seller_price"], "total": to_f(r["total_amount"]), "n": 1
        }

for k, u in sorted(units.items()):
    cost = get_cost(u["sku"])
    sp_str = f"{u['sp']}" if u["sp"] is not None else "NULL"
    sign = "+" if (u["sp"] or 0) > 0 else "−" if (u["sp"] or 0) < 0 else "?"
    print(f"  sku={u['sku']:>12}  unit={u['unit'][:25]:<25}  sp={sp_str:<10} ({sign})  "
          f"total={u['total']:>10,.2f}  cost={cost:>8.0f}  n={u['n']}")

print(f"\nВсего уникальных (sku, unit): {len(units)}")

print("\n═══ 3. SKU, которые есть в POSTING, но НЕ в realization ═══")
real = set(r[0] for r in c.execute(
    "SELECT DISTINCT sku FROM monthly_realization_rows WHERE month = ?", (month,)))
posting_skus = set(k[0] for k in units.keys())
only_posting = posting_skus - real
for sku in sorted(only_posting):
    cost = get_cost(sku)
    print(f"  sku={sku}  cost={cost}")

print("\n═══ 4. SKU из realization, которых НЕТ в POSTING ═══")
only_real = real - posting_skus
for sku in sorted(only_real):
    cost = get_cost(sku)
    print(f"  sku={sku}  cost={cost}")

c.close()