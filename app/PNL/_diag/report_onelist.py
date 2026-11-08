# -*- coding: utf-8 -*-
"""report_onelist.py — один лист: заказы/отказы/доставлено/возвраты/COGS по месяцам."""
import sqlite3, csv
from pathlib import Path
from collections import defaultdict

APP = Path(__file__).resolve().parents[2]
DB = APP / "ozon.db"
OUT = APP / "PNL" / "_reports"
OUT.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row

# себестоимость
prices = {}
for r in conn.execute("SELECT sku, cost_price FROM product_cost_history WHERE cost_price IS NOT NULL ORDER BY sku, date_from DESC, id DESC"):
    prices.setdefault(r["sku"], float(r["cost_price"]))
for r in conn.execute("SELECT sku, cost_price FROM products WHERE cost_price IS NOT NULL"):
    prices.setdefault(r["sku"], float(r["cost_price"]))

# 1. Заказы по месяцам и статусам
orders = defaultdict(lambda: {"total":0, "delivered":0, "cancelled":0, "delivering":0, "other":0})
for r in conn.execute("SELECT created_at, status FROM orders_created"):
    m = str(r["created_at"])[:7]
    s = (r["status"] or "unknown").lower()
    orders[m]["total"] += 1
    if s in orders[m]:
        orders[m][s] += 1
    else:
        orders[m]["other"] += 1

# 2. Realization по месяцам
real = defaultdict(lambda: {"buy_q":0, "buy_sum":0.0, "ret_q":0, "ret_sum":0.0})
for r in conn.execute("SELECT CAST(month AS TEXT) AS month, sku, quantity, is_return FROM monthly_realization_rows"):
    m = str(r["month"])[:7]
    q = r["quantity"] or 0
    c = prices.get(r["sku"], 0)
    v = c * q
    if r["is_return"] == 0:
        real[m]["buy_q"] += q; real[m]["buy_sum"] += v
    else:
        real[m]["ret_q"] += q; real[m]["ret_sum"] += v

months = sorted(set(list(orders.keys()) + list(real.keys())))

# 3. Один CSV
f = OUT / "report_onelist.csv"
fields = ["month", "orders_total", "orders_cancelled", "orders_delivered", "orders_delivering",
          "sales_qty", "sales_cogs", "returns_qty", "returns_cogs", "cogs_net"]
with f.open("w", newline="", encoding="utf-8-sig") as fh:
    w = csv.DictWriter(fh, fieldnames=fields)
    w.writeheader()
    for m in months:
        o = orders[m]; r = real[m]
        w.writerow({
            "month": m,
            "orders_total": o["total"],
            "orders_cancelled": o["cancelled"],
            "orders_delivered": o["delivered"],
            "orders_delivering": o["delivering"],
            "sales_qty": r["buy_q"],
            "sales_cogs": round(r["buy_sum"]),
            "returns_qty": r["ret_q"],
            "returns_cogs": round(r["ret_sum"]),
            "cogs_net": round(r["buy_sum"] - r["ret_sum"]),
        })

# 4. Печать на экран
print(f"{'месяц':<8} | {'заказы':>7} | {'отказы':>7} | {'доставл':>8} | {'в пути':>7} | "
      f"{'прод шт':>8} | {'COGS прод':>10} | {'возв шт':>8} | {'COGS возв':>10} | {'COGS итог':>10}")
print("-" * 118)
for m in months:
    o = orders[m]; r = real[m]
    print(f"{m:<8} | {o['total']:>7} | {o['cancelled']:>7} | {o['delivered']:>8} | {o['delivering']:>7} | "
          f"{r['buy_q']:>8} | {r['buy_sum']:>10.0f} | {r['ret_q']:>8} | {r['ret_sum']:>10.0f} | "
          f"{r['buy_sum']-r['ret_sum']:>10.0f}")

# Итого
tot_o = {k: sum(orders[m][k] for m in months) for k in ("total","cancelled","delivered","delivering")}
tot_r = {k: sum(real[m][k] for m in months) for k in ("buy_q","buy_sum","ret_q","ret_sum")}
print("-" * 118)
print(f"{'ИТОГО':<8} | {tot_o['total']:>7} | {tot_o['cancelled']:>7} | {tot_o['delivered']:>8} | {tot_o['delivering']:>7} | "
      f"{tot_r['buy_q']:>8} | {tot_r['buy_sum']:>10.0f} | {tot_r['ret_q']:>8} | {tot_r['ret_sum']:>10.0f} | "
      f"{tot_r['buy_sum']-tot_r['ret_sum']:>10.0f}")

print(f"\nСохранено: {f}")
conn.close()