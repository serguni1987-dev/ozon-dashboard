"""Проверяет 5 формул COGS против эталона Ozon."""
import sqlite3, sys, os
from collections import defaultdict
from openpyxl import load_workbook

MONTH = "2026-01"
OZON  = 147966
path  = sys.argv[1] if len(sys.argv) > 1 else "Отчет по начислениям_01.01.2026-31.01.2026.xlsx"

# --- Excel: продажи и возвраты по SKU ---
wb = load_workbook(path, read_only=True, data_only=True)
ws = wb.active
headers, hr = None, None
for i, row in enumerate(ws.iter_rows(values_only=True), 1):
    if row and row[0] == "ID начисления":
        headers = list(row); hr = i; break
idx = {n: i for i, n in enumerate(headers)}

ex_sales, ex_returns = defaultdict(int), defaultdict(int)
for row in ws.iter_rows(min_row=hr+1, values_only=True):
    if not row or len(row) <= idx["SKU"]: continue
    sku = row[idx["SKU"]]
    if not sku: continue
    try: sku = int(sku)
    except: continue
    grp = row[idx["Группа услуг"]]
    typ = row[idx["Тип начисления"]]
    try: q = abs(int(row[idx["Количество"]] or 1))
    except: q = 1
    if q == 0: q = 1
    if grp == "Продажи" and typ == "Выручка":
        ex_sales[sku] += q
    elif grp == "Возвраты" and typ == "Возврат выручки":
        ex_returns[sku] += q

# --- Realization ---
con = sqlite3.connect("ozon.db"); con.row_factory = sqlite3.Row
rl_sales, rl_returns = defaultdict(int), defaultdict(int)
for r in con.execute("SELECT sku, quantity, is_return FROM monthly_realization_rows WHERE month=?", (MONTH,)):
    q = r["quantity"] or 0
    if r["is_return"]:
        rl_returns[r["sku"]] += abs(q)
    else:
        rl_sales[r["sku"]] += q

# --- cost на конец месяца ---
y, m = MONTH.split("-")
ny, nm = (int(y)+1, 1) if m == "12" else (int(y), int(m)+1)
d2 = f"{ny}-{nm:02d}-01"

def cost_for(sku):
    r = con.execute("""SELECT cost_price FROM product_cost_history
        WHERE sku=? AND date_from < ?
        ORDER BY date_from DESC LIMIT 1""", (sku, d2)).fetchone()
    return float(r[0]) if r and r[0] else 0.0

# --- 5 вариантов ---
variants = {
    "1. Excel: продажи":                    lambda es, er, rs, rr: es,
    "2. Excel: продажи − возвраты":         lambda es, er, rs, rr: es - er,
    "3. Realization: продажи":              lambda es, er, rs, rr: rs,
    "4. Realization: продажи − возвраты":   lambda es, er, rs, rr: rs - rr,
    "5. Realization: продажи + возвраты":   lambda es, er, rs, rr: rs + rr,
}

totals = {k: 0.0 for k in variants}
skipped_no_cost = []
per_sku = {}

all_skus = sorted(set(list(ex_sales) + list(ex_returns) + list(rl_sales) + list(rl_returns)))
for sku in all_skus:
    c = cost_for(sku)
    if c == 0:
        skipped_no_cost.append((sku, ex_sales.get(sku,0), ex_returns.get(sku,0),
                                     rl_sales.get(sku,0), rl_returns.get(sku,0)))
        continue
    es, er = ex_sales.get(sku,0), ex_returns.get(sku,0)
    rs, rr = rl_sales.get(sku,0), rl_returns.get(sku,0)
    per_sku[sku] = {"cost": c, "es": es, "er": er, "rs": rs, "rr": rr}
    for name, fn in variants.items():
        totals[name] += c * fn(es, er, rs, rr)

print(f"═══ {MONTH}   Ozon эталон: {OZON:,} ═══")
print()
print(f"{'Формула':<38} | {'Сумма':>14} | {'Δ vs Ozon':>12} | {'Δ%':>7}")
print("-" * 82)
for name, val in totals.items():
    d = val - OZON
    pct = d / OZON * 100
    mark = "  ✓✓" if abs(pct) < 0.5 else ("  ✓" if abs(pct) < 2 else "")
    print(f"{name:<38} | {val:>14,.2f} | {d:>+12,.0f} | {pct:>+6.2f}%{mark}")

print()
print(f"SKU без cost_price: {len(skipped_no_cost)}")
for sku, es, er, rs, rr in skipped_no_cost[:30]:
    print(f"  sku={sku}  ex={es}с/{er}в  rl={rs}с/{rr}в")

# Топ-SKU по вкладу в разницу
print()
print("=== Топ-10 SKU по вкладу (по variant 4) ===")
items = []
for sku, v in per_sku.items():
    c = v["cost"]
    items.append((sku, v, c * (v["rs"] - v["rr"])))
items.sort(key=lambda x: -abs(x[2]))
for sku, v, val in items[:10]:
    print(f"  {sku}: cost={v['cost']:>8,.0f}  ex={v['es']}с/{v['er']}в  rl={v['rs']}с/{v['rr']}в  COGS={val:>10,.2f}")

con.close()
