"""find_missing_costs.py — какие SKU продавались, но без себестоимости."""
import sqlite3
c = sqlite3.connect("ozon.db")
c.row_factory = sqlite3.Row

print("=" * 90)
print("SKU ИЗ ОТЧЁТА РЕАЛИЗАЦИИ БЕЗ СЕБЕСТОИМОСТИ")
print("=" * 90)
print(f"{'SKU':>12} | {'offer_id':<22} | {'qty':>5} | {'slp':>12} | {'Название':<35}")
print("-" * 100)

for r in c.execute("""
    SELECT
        mr.sku,
        mr.offer_id,
        SUM(mr.quantity) AS qty,
        SUM(mr.sale_price) AS slp,
        p.name
    FROM monthly_realization_rows mr
    LEFT JOIN products p ON p.sku = mr.sku
    WHERE p.cost_price IS NULL OR p.cost_price = 0
    GROUP BY mr.sku
    ORDER BY slp DESC
"""):
    name = (r['name'] or '')[:35]
    off = (r['offer_id'] or '')[:22]
    print(f"{r['sku']:>12} | {off:<22} | {r['qty']:>5} | {r['slp']:>12,.2f} | {name}")

# Итог по этим SKU
print()
r = c.execute("""
    SELECT COUNT(DISTINCT mr.sku) AS n,
           SUM(mr.quantity) AS qty,
           SUM(mr.sale_price) AS slp
    FROM monthly_realization_rows mr
    LEFT JOIN products p ON p.sku = mr.sku
    WHERE p.cost_price IS NULL OR p.cost_price = 0
""").fetchone()
print(f"ИТОГО: SKU={r['n']}  qty={r['qty']}  sale_price={r['slp']:,.2f}")

# И их месяцы
print()
print("По месяцам:")
for r in c.execute("""
    SELECT mr.month, COUNT(DISTINCT mr.sku) AS n, SUM(mr.quantity) AS qty,
           SUM(mr.sale_price) AS slp
    FROM monthly_realization_rows mr
    LEFT JOIN products p ON p.sku = mr.sku
    WHERE p.cost_price IS NULL OR p.cost_price = 0
    GROUP BY mr.month ORDER BY mr.month
"""):
    print(f"  {r['month']}  SKU={r['n']:>3}  qty={r['qty']:>3}  sale_price={r['slp']:>10,.2f}")

c.close()