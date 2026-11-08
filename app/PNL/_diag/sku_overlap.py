# -*- coding: utf-8 -*-
"""sku_overlap.py — найти SKU, где у нас есть и выкуп, и возврат в одном месяце."""
import sqlite3
from pathlib import Path
from collections import defaultdict

APP = Path(__file__).resolve().parents[2]
DB = APP / "ozon.db"
TARGETS = {"2026-01": 150126.0, "2026-02": 104592.0}

conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row

db_prices = {}
for r in conn.execute("SELECT sku, cost_price FROM product_cost_history WHERE cost_price IS NOT NULL ORDER BY sku, date_from DESC, id DESC"):
    db_prices.setdefault(r["sku"], float(r["cost_price"]))
for r in conn.execute("SELECT sku, cost_price FROM products WHERE cost_price IS NOT NULL"):
    db_prices.setdefault(r["sku"], float(r["cost_price"]))

for month, target in TARGETS.items():
    rows = conn.execute("""
        SELECT sku, offer_id, item_name, quantity, is_return
        FROM monthly_realization_rows
        WHERE CAST(month AS TEXT) = ? OR CAST(month AS TEXT) LIKE ?
    """, (month, month + "%")).fetchall()

    per_sku = defaultdict(lambda: {"buy_q":0,"buy_sum":0.0,"ret_q":0,"ret_sum":0.0,"offer_id":"","item_name":""})
    total_buy = 0.0; total_ret = 0.0
    for r in rows:
        c = db_prices.get(r["sku"]); q = r["quantity"] or 0
        v = (c or 0) * q
        s = per_sku[r["sku"]]
        if r["offer_id"]: s["offer_id"] = r["offer_id"]
        if r["item_name"]: s["item_name"] = r["item_name"]
        if r["is_return"] == 0:
            s["buy_q"] += q; s["buy_sum"] += v; total_buy += v
        else:
            s["ret_q"] += q; s["ret_sum"] += v; total_ret += v

    print(f"\n{'='*100}")
    print(f"{month}  Точка={target:.0f}  наш buy={total_buy:.0f}  Δ={total_buy-target:+.0f}  ret={total_ret:.0f}")
    print(f"{'='*100}")

    # SKU где есть и выкуп, и возврат
    overlap = [sku for sku, s in per_sku.items() if s["buy_q"] > 0 and s["ret_q"] > 0]
    print(f"\nSKU с выкупом И возвратом в этом месяце: {len(overlap)}")
    for sku in overlap:
        s = per_sku[sku]
        print(f"  {sku:>12} | {s['offer_id']:<20} | buy qty={s['buy_q']} sum={s['buy_sum']:.0f} | ret qty={s['ret_q']} sum={s['ret_sum']:.0f} | net={s['buy_sum']-s['ret_sum']:+.0f}")

    # Все возвраты включая qty=0
    print(f"\nВсе возвраты (включая qty=0):")
    for r in rows:
        if r["is_return"] == 1:
            c = db_prices.get(r["sku"])
            cs = f"{c:.0f}" if c else "—"
            has_buy = per_sku[r["sku"]]["buy_q"] > 0
            print(f"  {r['sku']:>12} | {r['offer_id']:<20} | qty={r['quantity']} cost={cs:>8} | есть в выкупе: {has_buy}")

    # Полный список выкупа (все, не только ТОП-25)
    print(f"\nПОЛНЫЙ список выкупа ({len([1 for r in rows if r['is_return']==0])} строк):")
    buy_items = []
    for sku, s in per_sku.items():
        if s["buy_q"] > 0:
            buy_items.append((sku, s["offer_id"], s["buy_q"], db_prices.get(sku, 0), s["buy_sum"]))
    buy_items.sort(key=lambda x: -x[4])
    for sku, oid, qty, c, contrib in buy_items:
        print(f"  {sku:>12} | {oid:<20} | qty={qty:>3} | cost={c:>8.0f} | sum={contrib:>8.0f}")

conn.close()