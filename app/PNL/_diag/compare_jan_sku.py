"""Сверка января: Excel начисления vs monthly_realization_rows по SKU.
Использование:
    py PNL\_diag\compare_jan_sku.py "путь\к\Отчет_по_начислениям_01.01.2026-31.01.2026.xlsx"
"""
import sqlite3, sys, os
from collections import defaultdict

path_xlsx = sys.argv[1] if len(sys.argv) > 1 else "Отчет по начислениям_01.01.2026-31.01.2026.xlsx"

try:
    from openpyxl import load_workbook
except ImportError:
    print("Нужен openpyxl: pip install openpyxl")
    sys.exit(1)

if not os.path.exists(path_xlsx):
    print(f"Файл не найден: {path_xlsx}")
    sys.exit(1)

wb = load_workbook(path_xlsx, read_only=True, data_only=True)
ws = wb.active

# Найти строку заголовков
headers, header_row = None, None
for i, row in enumerate(ws.iter_rows(values_only=True), 1):
    if row and row[0] == "ID начисления":
        headers = list(row); header_row = i; break
if not headers:
    print("Не нашёл заголовок 'ID начисления'")
    sys.exit(1)

idx = {name: i for i, name in enumerate(headers)}
print("Колонки:", list(idx.keys()))
col_grp = idx.get("Группа услуг")
col_typ = idx.get("Тип начисления")
col_sku = idx.get("SKU")
col_qty = idx.get("Количество")
print()

ex_sales = defaultdict(int)
ex_returns = defaultdict(int)

def to_int(v):
    try: return int(v)
    except: return 0

for row in ws.iter_rows(min_row=header_row+1, values_only=True):
    if not row: continue
    if len(row) <= col_sku: continue
    sku = row[col_sku]
    if not sku: continue
    try: sku = int(sku)
    except: continue
    grp = row[col_grp] if col_grp < len(row) else None
    typ = row[col_typ] if col_typ < len(row) else None
    qty = abs(to_int(row[col_qty])) if col_qty < len(row) else 1
    if not qty: qty = 1

    if grp == "Продажи" and typ == "Выручка":
        ex_sales[sku] += qty
    elif grp == "Возвраты" and typ == "Возврат выручки":
        ex_returns[sku] += qty

print(f"Excel: продано всего = {sum(ex_sales.values())}  (SKU: {len(ex_sales)})")
print(f"Excel: возвращено     = {sum(ex_returns.values())}  (SKU: {len(ex_returns)})")
print()

con = sqlite3.connect("ozon.db"); con.row_factory = sqlite3.Row
rl_sales = defaultdict(int)
rl_returns = defaultdict(int)
for r in con.execute("""
    SELECT sku, quantity, is_return FROM monthly_realization_rows WHERE month='2026-01'
"""):
    sku = r["sku"]
    qty = r["quantity"] or 0
    if r["is_return"]:
        rl_returns[sku] += abs(qty)
    else:
        rl_sales[sku] += qty

print(f"Realization: продано = {sum(rl_sales.values())}  (SKU: {len(rl_sales)})")
print(f"Realization: возвратов = {sum(rl_returns.values())}  (SKU: {len(rl_returns)})")
print()

all_skus = sorted(set(ex_sales)|set(ex_returns)|set(rl_sales)|set(rl_returns))
print(f"{'sku':>12} | {'ex_прод':>8} | {'ex_возвр':>9} | {'rl_прод':>8} | {'rl_возвр':>9} | {'Δ':>6}")
print("-" * 70)

only_ex, only_rl, diffs = [], [], []
for sku in all_skus:
    es = ex_sales.get(sku, 0); er = ex_returns.get(sku, 0)
    rs = rl_sales.get(sku, 0); rr = rl_returns.get(sku, 0)
    d = rs - es
    mark = ""
    if es == 0 and rs > 0: only_rl.append(sku); mark = " ←только RL"
    elif es > 0 and rs == 0: only_ex.append(sku); mark = " ←только EX"
    elif d != 0: diffs.append((sku, es, rs))
    if d != 0 or er != 0 or rr != 0:
        print(f"{sku:>12} | {es:>8} | {er:>9} | {rs:>8} | {rr:>9} | {d:>+6}{mark}")

print()
print(f"Только в Excel (продажи, но нет в realization): {len(only_ex)}")
for s in only_ex: print(f"  {s}: ex_прод={ex_sales.get(s,0)} ex_возвр={ex_returns.get(s,0)}")

print(f"\nТолько в Realization: {len(only_rl)}")
for s in only_rl: print(f"  {s}: rl_прод={rl_sales.get(s,0)}")

print(f"\nРасхождение по проданному кол-ву: {len(diffs)} SKU")
for s, es, rs in diffs: print(f"  {s}: excel={es}  real={rs}  Δ={rs-es:+}")

con.close()
