"""Сверка наших данных с эталоном Ozon за 01.09-03.10.2026."""
import sqlite3
from pathlib import Path

DB = Path(r"C:\Users\sergu\Desktop\проект\app\ozon.db")
D1, D2 = "2026-09-01", "2026-10-03"

# Эталон (из xlsx Ozon)
REF = {
    "orders":           64,
    "orders_rub":       723784.0,
    "purchased":        21,
    "cancelled":        38,
    "returned":         1,
    "seller_price":     238113.0,
    "sale_price":       190490.0,
    "cogs":             78353.0,
    "commission":       121001.96,
    "logistics":        13594.03,
    "other_mp":         5912.59,
    "total_mp":         140508.58,
    "margin":           19251.42,
    "tax":              13334.0,
    "profit":           5917.0,
}

# Группы type_id (как в calc_margin.py)
LOGISTICS_IDS = {16,17,28,29,30,32,38,39,42,43,44,45,59,73,98,12}
AGENTS_IDS    = {1,74,79,45,63,66,68,122,123}
FBO_IDS       = {21,46,71,76,84,85,86,97,108,109,111,131,132}
MARKETING_IDS = {3,4,5,19,22,23,31,33,41,47,48,49,50,54,55,61,70,80,87,95,96,116,130}

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

# 1) realization_daily — выкупы, выручка, комиссия, логистика (из delivery_total)
r = con.execute("""
    SELECT
        SUM(CASE WHEN seller_price > 0 THEN quantity ELSE 0 END)
      - SUM(CASE WHEN seller_price < 0 THEN quantity ELSE 0 END) AS q,
        SUM(seller_price)  AS seller,
        SUM(sale_price)    AS sale,
        SUM(commission)    AS comm,
        SUM(delivery_total) AS dl
    FROM realization_daily
    WHERE date BETWEEN ? AND ?
      AND (seller_price != 0 OR commission != 0)
""", (D1, D2)).fetchone()

our_seller = r["seller"] or 0
our_sale = r["sale"] or 0
our_q = r["q"] or 0
our_comm = abs(r["comm"] or 0)
our_dl_from_realiz = abs(r["dl"] or 0)  # это НЕ финальная логистика, дублирует accrual_sku

# 2) accrual_sku_daily — по группам
log = agg = fbo = mkt = other = 0
for row in con.execute("""
    SELECT type_id, SUM(amount) AS s FROM accrual_sku_daily
    WHERE date BETWEEN ? AND ? GROUP BY type_id
""", (D1, D2)):
    amt = abs(row["s"] or 0)
    tid = row["type_id"]
    if tid in LOGISTICS_IDS: log += amt
    elif tid in AGENTS_IDS:  agg += amt
    elif tid in FBO_IDS:     fbo += amt
    elif tid in MARKETING_IDS: mkt += amt
    else: other += amt

# 3) non_item — аллокация по выручке SKU (как в calc_margin)
rows = con.execute("""
    SELECT a.date, a.posting_number, a.type_id, a.amount,
           r.sku, r.seller_price AS sku_amount
    FROM accrual_non_item_daily a
    JOIN realization_daily r
      ON r.date = a.date AND r.posting_number = a.posting_number
    WHERE a.date BETWEEN ? AND ?
      AND r.seller_price > 0 AND r.commission < 0
""", (D1, D2)).fetchall()

posting_total = {}
for r in rows:
    key = (r["date"], r["posting_number"])
    posting_total[key] = posting_total.get(key, 0) + (r["sku_amount"] or 0)

for r in rows:
    key = (r["date"], r["posting_number"])
    total = posting_total.get(key, 0)
    if not total: continue
    share = (r["sku_amount"] or 0) / total
    amt = abs(r["amount"] or 0) * share
    tid = r["type_id"]
    if tid in LOGISTICS_IDS: log += amt
    elif tid in AGENTS_IDS:  agg += amt
    elif tid in FBO_IDS:     fbo += amt
    elif tid in MARKETING_IDS: mkt += amt
    else: other += amt

# 4) sales_daily — заказы/отмены/возвраты
r = con.execute("""
    SELECT SUM(orders_units) AS o, SUM(cancelled) AS c,
           SUM(returned_by_order_date) AS rt
    FROM sales_daily WHERE date BETWEEN ? AND ?
""", (D1, D2)).fetchone()
our_orders = int(r["o"] or 0)
our_cancelled = int(r["c"] or 0)
our_returned = int(r["rt"] or 0)

# 5) себестоимость
cogs = 0
for r in con.execute("""
    SELECT sku, SUM(quantity) AS q FROM realization_daily
    WHERE date BETWEEN ? AND ? AND seller_price > 0 AND commission < 0
    GROUP BY sku
""", (D1, D2)):
    q = r["q"] or 0
    if q <= 0: continue
    c = con.execute("""
        SELECT cost_price FROM product_cost_history
        WHERE sku = ? AND date_from <= ? ORDER BY date_from DESC LIMIT 1
    """, (r["sku"], D2)).fetchone()
    if c and c[0]: cogs += c[0] * q

con.close()

# Итоги
our_other_mp = agg + fbo + other
our_total_mp = our_comm + log + our_other_mp + mkt
our_margin = our_seller - cogs - our_total_mp
our_tax_base = our_sale
our_tax = our_tax_base * 0.07
our_profit = our_margin - our_tax

# Сверка
def cmp(name, ours, ref):
    d = ours - ref
    mark = "OK" if abs(d) < 1 else "!!"
    print(f"  {name:<30} ours={ours:>14,.2f}  ref={ref:>14,.2f}  diff={d:>+12,.2f}  {mark}")

print(f"=== Сверка 01.09-03.10.2026 (наши vs эталон) ===")
print()
cmp("Заказы, шт.", our_orders, REF["orders"])
cmp("Заказы, ₽", 0, REF["orders_rub"])  # мы не считаем orders_rub здесь
cmp("Выкупы, шт.", our_q, REF["purchased"])
cmp("Отмены, шт.", our_cancelled, REF["cancelled"])
cmp("Возвраты, шт.", our_returned, REF["returned"])
print()
cmp("Выручка (seller_price)", our_seller, REF["seller_price"])
cmp("Налоговая база (sale_price)", our_tax_base, REF["sale_price"])
cmp("Себестоимость", cogs, REF["cogs"])
print()
cmp("Комиссия МП", our_comm, REF["commission"])
cmp("Логистика МП", log, REF["logistics"])
cmp("Прочие расходы МП", our_other_mp, REF["other_mp"])
cmp("Реклама", mkt, 0)  # в эталоне 0
cmp("Всего расходов МП", our_total_mp, REF["total_mp"])
print()
cmp("Маржа", our_margin, REF["margin"])
cmp("Налоги (7%)", our_tax, REF["tax"])
cmp("Прибыль", our_profit, REF["profit"])
print()
print(f"Расшифровка Прочих:")
print(f"  agents = {agg:,.2f}")
print(f"  fbo    = {fbo:,.2f}")
print(f"  other  = {other:,.2f}")
