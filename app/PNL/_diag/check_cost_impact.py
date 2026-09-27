import csv, sqlite3

CSV = r"C:\Users\sergu\Desktop\проект\costs_all.csv"
DB = "ozon.db"

with open(CSV, encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f, delimiter=";"))

empty_offers = [r["offer_id"] for r in rows if not r["cost_price"].strip()]
print(f"SKU без цены: {len(empty_offers)}")

c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row

# Сколько из них продавались (в monthly_realization_rows)?
sold = []
for offer in empty_offers:
    r = c.execute("""
        SELECT mr.sku, mr.offer_id,
               SUM(mr.quantity) AS qty,
               SUM(mr.sale_price) AS slp
        FROM monthly_realization_rows mr
        WHERE mr.offer_id = ?
        GROUP BY mr.sku
    """, (offer,)).fetchone()
    if r and r["qty"]:
        sold.append(dict(r))

print(f"Из них продавались: {len(sold)}")
print(f"Сумма продаж (без цены): {sum(s['slp'] or 0 for s in sold):,.2f} ₽")
print()

if sold:
    print("Топ-15 продававшихся без цены:")
    for s in sorted(sold, key=lambda x: -(x["slp"] or 0))[:15]:
        print(f"  {s['offer_id']:<25} sku={s['sku']:<12} qty={s['qty']:>3} slp={s['slp']:>10,.2f}")

# Дубли
dups = [o for o in empty_offers if "дубл" in o.lower()]
print()
print(f"Из них 'дубл_': {len(dups)}")

c.close()