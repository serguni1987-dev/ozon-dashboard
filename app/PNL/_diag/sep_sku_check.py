# -*- coding: utf-8 -*-
"""sep_sku_check.py — сверка сентября по артикулам:
   Ozon XLSX (лист 'По товарам', header=1) vs monthly_realization_rows + COGS.
"""
import sqlite3
from pathlib import Path
from collections import defaultdict

import pandas as pd

APP = Path(__file__).resolve().parents[2]
DB = APP / "ozon.db"
XLSX = Path(r"C:\Users\sergu\Desktop\проект\analytics_report_daily_2026-10-12_00_28.xlsx")
MONTH = "2026-09"
MONTH_END = "2026-09-30"   # для выбора версии себестоимости

# ── 1. XLSX ──
print(f"Читаю XLSX: {XLSX}")
df = pd.read_excel(XLSX, sheet_name="По товарам", header=1)
df = df.rename(columns={df.columns[0]: "Артикул", df.columns[1]: "День"})
df.columns = [str(c).replace("\n", " ").replace("  ", " ").strip() for c in df.columns]

def find_col(*needles):
    for c in df.columns:
        s = c.lower()
        if all(n.lower() in s for n in needles):
            return c
    return None

col_sku = "Артикул"
col_day = "День"
col_ord = find_col("Заказано товаров")
col_del = find_col("Доставлено")
col_buy = find_col("Выкуплено")
can_on_order = find_col("Отменено", "на дату заказа")
ret_on_order = find_col("Возвращено", "на дату заказа")

df[col_day] = pd.to_datetime(df[col_day], errors="coerce")
df[col_sku] = df[col_sku].astype(str).str.strip()
df = df.dropna(subset=[col_day])
df = df[df[col_sku] != "–"]
df = df[df[col_day].dt.strftime("%Y-%m") == MONTH].copy()

num_cols = [c for c in [col_ord, col_del, col_buy, can_on_order, ret_on_order] if c]
for c in num_cols:
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

agg = df.groupby(col_sku)[num_cols].sum()

# ── 2. БД ──
conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row

# offer_id ↔ sku
offer_to_sku = {}
sku_to_offer = {}
for r in conn.execute("SELECT sku, offer_id FROM products WHERE offer_id IS NOT NULL"):
    o = str(r["offer_id"]).strip()
    offer_to_sku[o] = r["sku"]
    sku_to_offer[r["sku"]] = o

# Реализация за месяц: продажи и возвраты
real = defaultdict(lambda: {"buy_q": 0, "ret_q": 0})
for r in conn.execute("""
    SELECT offer_id, sku, quantity, is_return
    FROM monthly_realization_rows
    WHERE CAST(month AS TEXT) LIKE ?
""", (MONTH + "%",)):
    o = str(r["offer_id"]).strip() if r["offer_id"] else str(r["sku"])
    q = r["quantity"] or 0
    if r["is_return"] == 0:
        real[o]["buy_q"] += q
    else:
        real[o]["ret_q"] += q

# Себестоимость на конец месяца
def cost_for(offer_id):
    sku = offer_to_sku.get(offer_id)
    if sku is None:
        return None
    row = conn.execute("""
        SELECT cost_price FROM product_cost_history
        WHERE sku = ? AND date_from <= ?
        ORDER BY date_from DESC LIMIT 1
    """, (sku, MONTH_END)).fetchone()
    if row and row["cost_price"]:
        return float(row["cost_price"])
    row = conn.execute("SELECT cost_price FROM products WHERE sku = ?", (sku,)).fetchone()
    if row and row["cost_price"]:
        return float(row["cost_price"])
    return None

name_map = {str(r["offer_id"]).strip(): (r["name"] or "")[:32]
            for r in conn.execute("SELECT offer_id, name FROM products WHERE offer_id IS NOT NULL")}

# ── 3. Сводная таблица ──
all_offers = sorted(set(agg.index) | set(real.keys()))

print("\n" + "=" * 165)
print(f"СВЕРКА + COGS за {MONTH}   (себест. на {MONTH_END})")
print("=" * 165)
hdr = (f"{'offer_id':<18} | {'название':<30} | "
       f"{'зак':>4} | {'дос':>4} | {'вык':>4} | {'отм':>4} | {'воз':>4} | "
       f"{'прод':>5} | {'воз':>4} | {'Δ':>4} | "
       f"{'себест':>8} | {'COGS_прод':>10} | {'COGS_воз':>9} | {'COGS_net':>10}")
print(hdr); print("-" * len(hdr))

totals = defaultdict(float)
skus_with_diff = []
skus_no_cost = []

for o in all_offers:
    def g(col):
        return int(agg.loc[o, col]) if (o in agg.index and col) else 0

    x_ord = g(col_ord); x_del = g(col_del); x_buy = g(col_buy)
    x_can = g(can_on_order); x_ret = g(ret_on_order)

    m_buy = real[o]["buy_q"]; m_ret = real[o]["ret_q"]
    delta = m_buy - x_buy
    cost = cost_for(o)

    cogs_buy = (cost or 0) * m_buy
    cogs_ret = (cost or 0) * m_ret
    cogs_net = cogs_buy - cogs_ret

    totals["x_ord"] += x_ord; totals["x_del"] += x_del; totals["x_buy"] += x_buy
    totals["x_can"] += x_can; totals["x_ret"] += x_ret
    totals["m_buy"] += m_buy; totals["m_ret"] += m_ret
    totals["cogs_buy"] += cogs_buy
    totals["cogs_ret"] += cogs_ret
    totals["cogs_net"] += cogs_net

    if x_ord == 0 and m_buy == 0 and m_ret == 0:
        continue

    name = name_map.get(o, "")
    mark = "  <<<" if delta != 0 else ""
    cost_s = f"{cost:.2f}" if cost is not None else "???"
    if cost is None and (m_buy or m_ret):
        skus_no_cost.append((o, name, m_buy, m_ret))

    print(f"{o:<18} | {name:<30} | "
          f"{x_ord:>4} | {x_del:>4} | {x_buy:>4} | {x_can:>4} | {x_ret:>4} | "
          f"{m_buy:>5} | {m_ret:>4} | {delta:>+4} | "
          f"{cost_s:>8} | {cogs_buy:>10.2f} | {cogs_ret:>9.2f} | {cogs_net:>10.2f}{mark}")

    if delta != 0:
        skus_with_diff.append((o, name, x_buy, m_buy, delta))

print("-" * len(hdr))
print(f"{'ИТОГО':<18} | {'':<30} | "
      f"{totals['x_ord']:>4.0f} | {totals['x_del']:>4.0f} | {totals['x_buy']:>4.0f} | "
      f"{totals['x_can']:>4.0f} | {totals['x_ret']:>4.0f} | "
      f"{totals['m_buy']:>5.0f} | {totals['m_ret']:>4.0f} | "
      f"{totals['m_buy'] - totals['x_buy']:>+4.0f} | "
      f"{'':>8} | {totals['cogs_buy']:>10.2f} | {totals['cogs_ret']:>9.2f} | {totals['cogs_net']:>10.2f}")

print(f"\nАртикулов с расхождением: {len(skus_with_diff)}")
print(f"Артикулов без себестоимости: {len(skus_no_cost)}")
if skus_no_cost:
    print("\n⚠️  Нет себестоимости (COGS для них = 0, P&L занижен):")
    for o, name, mb, mr in skus_no_cost:
        print(f"  {o:<18} | {name:<30} | прод={mb} воз={mr}")

conn.close()