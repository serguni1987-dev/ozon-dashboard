# -*- coding: utf-8 -*-
"""cogs_diff_sku.py — сравнение цены БД vs XLSX по каждому проданному SKU."""
import sqlite3
from pathlib import Path
from collections import defaultdict
import pandas as pd

APP = Path(__file__).resolve().parents[2]
DB = APP / "ozon.db"
XLSX = Path(r"C:\Users\sergu\Desktop\проект\Себестоимость_на_дату-209648-dfcc96b9_150007_eb898994.xlsx")

TARGETS = {"2026-01": 150126.0, "2026-02": 104592.0}

conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row

# ── products: offer_id (upper) → sku ──
offer_to_sku = {}
for r in conn.execute("SELECT sku, offer_id FROM products WHERE offer_id IS NOT NULL"):
    offer_to_sku[str(r["offer_id"]).strip().upper()] = r["sku"]

# ── DB prices ──
db_prices = {}
for r in conn.execute("SELECT sku, cost_price FROM product_cost_history WHERE cost_price IS NOT NULL ORDER BY sku, date_from DESC, id DESC"):
    db_prices.setdefault(r["sku"], float(r["cost_price"]))
for r in conn.execute("SELECT sku, cost_price FROM products WHERE cost_price IS NOT NULL"):
    db_prices.setdefault(r["sku"], float(r["cost_price"]))
print("DB prices:", len(db_prices))

# ── XLSX ──
df = pd.read_excel(XLSX)
df = df.dropna(subset=["Артикул"]).copy()
df["Артикул"] = df["Артикул"].astype(str).str.strip().str.upper()
df["Себестоимость"] = pd.to_numeric(df["Себестоимость"], errors="coerce")
df["Unnamed: 6"] = pd.to_numeric(df["Unnamed: 6"], errors="coerce")

# ── XLSX-цены по SKU ──
xl_sebest = defaultdict(list)
xl_unnamed = defaultdict(list)
for _, row in df.iterrows():
    sku = offer_to_sku.get(row["Артикул"])
    if sku is None:
        continue
    if row["Себестоимость"] > 0:
        xl_sebest[sku].append(float(row["Себестоимость"]))
    if pd.notna(row["Unnamed: 6"]) and row["Unnamed: 6"] > 0:
        xl_unnamed[sku].append(float(row["Unnamed: 6"]))

print("XLSX SKU с Себест>0:", len(xl_sebest))
print("XLSX SKU с Unnamed6>0:", len(xl_unnamed))

# ── realization per month ──
def load_month(month):
    return conn.execute("""
        SELECT sku, offer_id, quantity, is_return
        FROM monthly_realization_rows
        WHERE CAST(month AS TEXT) = ? OR CAST(month AS TEXT) LIKE ?
    """, (month, month + "%")).fetchall()

def calc(rows, price_map):
    buy=0.0; ret=0.0; ret_sold=0.0
    sold = {r["sku"] for r in rows if r["is_return"]==0}
    for r in rows:
        c = price_map.get(r["sku"]); q = r["quantity"] or 0
        if c is None: continue
        v = c*q
        if r["is_return"]==0: buy += v
        elif r["is_return"]==1:
            ret += v
            if r["sku"] in sold: ret_sold += v
    return buy, ret, ret_sold

# ── Сводка по правилам ──
def pick_last(l): return l[-1] if l else None
def pick_first(l): return l[0] if l else None
def pick_max(l): return max(l) if l else None
def pick_min(l): return min(l) if l else None
def pick_avg(l): return sum(l)/len(l) if l else None

rules = {
    "DB (current)":        db_prices,
    "XLSX Себест last":    {k: pick_last(v) for k,v in xl_sebest.items() if pick_last(v)},
    "XLSX Себест first":   {k: pick_first(v) for k,v in xl_sebest.items() if pick_first(v)},
    "XLSX Себест max":     {k: pick_max(v) for k,v in xl_sebest.items()},
    "XLSX Себест min":     {k: pick_min(v) for k,v in xl_sebest.items()},
    "XLSX Себест avg":     {k: pick_avg(v) for k,v in xl_sebest.items() if pick_avg(v)},
    "XLSX Unnamed6 last":  {k: pick_last(v) for k,v in xl_unnamed.items() if pick_last(v)},
    "XLSX Unnamed6 max":   {k: pick_max(v) for k,v in xl_unnamed.items()},
}

for month, target in TARGETS.items():
    print(f"\n{'='*100}")
    print(f"{month}   Точка = {target:.0f}")
    print(f"{'='*100}")
    print(f"{'rule':<22} | {'buy':>10} | {'buy-all':>10} | {'buy-sold':>10} | {'Δbuy':>8} | {'Δall':>8} | {'Δsold':>8}")
    print("-"*104)
    for name, pm in rules.items():
        b, ra, rs = calc(load_month(month), pm)
        print(f"{name:<22} | {b:>10.0f} | {b-ra:>10.0f} | {b-rs:>10.0f} | {b-target:>+8.0f} | {b-ra-target:>+8.0f} | {b-rs-target:>+8.0f}")

# ── Разложение Δ по SKU для DB-цены ──
for month, target in TARGETS.items():
    print(f"\n{'='*100}")
    print(f"{month}: разложение Δ по SKU (DB-цена, buy=выкуп)")
    print(f"{'='*100}")

    rows = load_month(month)
    per_sku = defaultdict(lambda: {"qty":0, "offer_id":"", "has_ret":False})
    for r in rows:
        if r["is_return"]==0:
            per_sku[r["sku"]]["qty"] += r["quantity"] or 0
            if r["offer_id"]: per_sku[r["sku"]]["offer_id"] = r["offer_id"]

    items = []
    total = 0
    for sku, v in per_sku.items():
        c = db_prices.get(sku)
        if c is None: continue
        contrib = c * v["qty"]
        total += contrib
        xl = xl_sebest.get(sku, [])
        items.append((sku, v["offer_id"], v["qty"], c, xl, contrib))

    items.sort(key=lambda x: -x[5])
    print(f"ИТОГО buy = {total:.0f}   Δ vs Точка = {total-target:+.0f}")
    print(f"\nТОП-25 SKU по вкладу:")
    print(f"{'sku':>12} | {'offer_id':<20} | {'qty':>4} | {'DB':>8} | {'XLSX prices':<30} | {'contrib':>10}")
    print("-"*100)
    for sku, oid, qty, c, xl, contrib in items[:25]:
        xls = ",".join(f"{p:.0f}" for p in xl[:4]) if xl else "—"
        print(f"{sku:>12} | {oid:<20} | {qty:>4} | {c:>8.0f} | {xls:<30} | {contrib:>10.0f}")

conn.close()