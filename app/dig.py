import sqlite3
con = sqlite3.connect("ozon.db")
con.row_factory = sqlite3.Row

SKU = 5236662414  # VL007E4 — самый показательный

print("=" * 70)
print(f"1) ВСЕ НАЧИСЛЕНИЯ по SKU={SKU} за август 2026")
print("=" * 70)
for r in con.execute("""
    SELECT type_id, type_name, SUM(amount) AS total, COUNT(*) AS cnt
    FROM accruals_services
    WHERE sku = ? AND date >= '2026-08-01' AND date < '2026-09-01'
    GROUP BY type_id, type_name
    ORDER BY ABS(SUM(amount)) DESC
""", (SKU,)):
    print(f"  type_id={r['type_id']:>4}  "
          f"amount={r['total']:>12,.2f}  "
          f"cnt={r['cnt']:>3}  "
          f"name={r['type_name']}")

print()
print("=" * 70)
print(f"2) sales_daily по дням для SKU={SKU}")
print("=" * 70)
for r in con.execute("""
    SELECT date, orders_units, purchased, cancelled,
           returned_by_order_date, avg_price, discount_pct
    FROM sales_daily
    WHERE sku = ? AND date >= '2026-08-01' AND date < '2026-09-01'
    ORDER BY date
""", (SKU,)):
    print(f"  {r['date']}  orders={r['orders_units']}  "
          f"purchased={r['purchased']}  cancelled={r['cancelled']}  "
          f"returned={r['returned_by_order_date']}  avg={r['avg_price']}")

print()
print("=" * 70)
print(f"3) realization для SKU={SKU}, август")
print("=" * 70)
for r in con.execute("""
    SELECT month, is_return, SUM(quantity) AS q,
           SUM(seller_price) AS sp, SUM(sale_price) AS slp,
           SUM(bonus) AS b, SUM(coinvestment) AS ci,
           SUM(gross_commission) AS gc, SUM(logistics) AS lg
    FROM monthly_realization_rows
    WHERE sku = ? AND month = '2026-08'
    GROUP BY month, is_return
""", (SKU,)):
    print(f"  is_return={r['is_return']}  qty={r['q']}  "
          f"seller_price={r['sp']}  sale_price={r['slp']}  "
          f"bonus={r['b']}  coinv={r['ci']}  "
          f"commission={r['gc']}  logistics={r['lg']}")