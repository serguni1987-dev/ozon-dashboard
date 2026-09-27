"""Прогоняет 5 вариантов COGS по всем месяцам, где есть Excel + эталон Ozon."""
import sqlite3, os, sys
from collections import defaultdict
from openpyxl import load_workbook

REF = {
    "2026-01": 147966, "2026-02": 104799, "2026-03": 44239,
    "2026-04": 28084,  "2026-05": 30861,  "2026-06": 6302,
    "2026-08": 112905,
}

# где искать Excel-файлы
EXCEL_DIR = os.path.expanduser("~/Downloads")

con = sqlite3.connect("ozon.db"); con.row_factory = sqlite3.Row

def cost_for(sku, d2):
    r = con.execute("""SELECT cost_price FROM product_cost_history
        WHERE sku=? AND date_from < ? ORDER BY date_from DESC LIMIT 1""",
        (sku, d2)).fetchone()
    return float(r[0]) if r and r[0] else 0.0

def find_excel(month):
    # ищем файл "Отчет по начислениям_01.MM.YYYY-..."
    y, m = month.split("-")
    for fn in os.listdir(EXCEL_DIR):
        if "Отчет по начислениям" not in fn: continue
        if f".{m}.{y}" in fn and fn.endswith(".xlsx"):
            return os.path.join(EXCEL_DIR, fn)
    return None

def load_excel(path):
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    headers, hr = None, None
    for i, row in enumerate(ws.iter_rows(values_only=True), 1):
        if row and row[0] == "ID начисления":
            headers = list(row); hr = i; break
    idx = {n: i for i, n in enumerate(headers)}
    sales, rets = defaultdict(int), defaultdict(int)
    for row in ws.iter_rows(min_row=hr+1, values_only=True):
        if not row or len(row) <= idx["SKU"]: continue
        sku = row[idx["SKU"]]
        if not sku: continue
        try: sku = int(sku)
        except: continue
        g, t = row[idx["Группа услуг"]], row[idx["Тип начисления"]]
        try: q = abs(int(row[idx["Количество"]] or 1))
        except: q = 1
        if q == 0: q = 1
        if g == "Продажи" and t == "Выручка": sales[sku] += q
        elif g == "Возвраты" and t == "Возврат выручки": rets[sku] += q
    return sales, rets

print(f"{'Мес':<8} | {'Ozon':>9} | {'#1 продажи':>12} | {'#2 прод−воз':>13} | "
      f"{'#3 real':>10} | {'#4 real−воз':>12} | {'#6 сейчас':>11}")
print("-" * 100)

def current_cogs(month):
    y, m = month.split("-"); ny, nm = (int(y)+1, 1) if m == "12" else (int(y), int(m)+1)
    d1, d2 = f"{y}-{m}-02"[:10], f"{ny}-{nm:02d}-01"
    d1 = f"{y}-{m}-01"
    skus = [r[0] for r in con.execute(
        "SELECT DISTINCT sku FROM monthly_realization_rows WHERE month=?", (month,))]
    total = 0.0
    for sku in skus:
        c = cost_for(sku, d2)
        if c == 0: continue
        r = con.execute("""SELECT SUM(delivered) FROM sales_daily
            WHERE sku=? AND date>=? AND date<?""", (sku, d1, d2)).fetchone()
        dlv = float(r[0] or 0) if r else 0
        if dlv > 0:
            total += c * dlv; continue
        r = con.execute("""SELECT SUM(sign) FROM (
            SELECT DISTINCT a.unit_number,
                CASE WHEN a.seller_price>0 THEN 1
                     WHEN a.seller_price<0 THEN -1 ELSE 0 END AS sign
            FROM accruals a WHERE a.sku=? AND a.date>=? AND a.date<?
              AND a.accrued_category='POSTING' AND a.seller_price IS NOT NULL)""",
            (sku, d1, d2)).fetchone()
        u = int(r[0] or 0) if r else 0
        if u: total += c * u
    return total

for month, ozon in REF.items():
    path = find_excel(month)
    if not path:
        print(f"{month:<8} | {ozon:>9,.0f} | {'Excel не найден':>60}")
        continue
    es, er = load_excel(path)
    y, m = month.split("-"); ny, nm = (int(y)+1, 1) if m == "12" else (int(y), int(m)+1)
    d2 = f"{ny}-{nm:02d}-01"

    rl_s, rl_r = defaultdict(int), defaultdict(int)
    for r in con.execute("""SELECT sku, quantity, is_return FROM monthly_realization_rows
        WHERE month=?""", (month,)):
        q = r["quantity"] or 0
        (rl_r if r["is_return"] else rl_s)[r["sku"]] += abs(q)

    v1 = v2 = v3 = v4 = 0.0
    all_skus = set(list(es)+list(er)+list(rl_s)+list(rl_r))
    for sku in all_skus:
        c = cost_for(sku, d2)
        if c == 0: continue
        v1 += c * es.get(sku, 0)
        v2 += c * (es.get(sku, 0) - er.get(sku, 0))
        v3 += c * rl_s.get(sku, 0)
        v4 += c * (rl_s.get(sku, 0) - rl_r.get(sku, 0))
    v6 = current_cogs(month)

    def fmt(v): return f"{v:>12,.0f}" if v else f"{'—':>12}"
    def pct(v): return f"{(v-ozon)/ozon*100:>+5.1f}%" if ozon else ""

    print(f"{month:<8} | {ozon:>9,.0f} | {fmt(v1)} | {fmt(v2)} {pct(v2):>5} | "
          f"{fmt(v3):>10} | {fmt(v4)} | {fmt(v6)} {pct(v6):>5}")

con.close()
