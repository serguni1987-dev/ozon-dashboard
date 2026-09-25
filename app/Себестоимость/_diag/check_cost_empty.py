import csv

CSV = r"C:\Users\sergu\Desktop\проект\costs_all.csv"

with open(CSV, encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f, delimiter=";"))

empty = [r for r in rows if not r["cost_price"].strip()]

print(f"Всего строк: {len(rows)}")
print(f"С ценой: {len(rows) - len(empty)}")
print(f"Без цены: {len(empty)}")
print()
print("Первые 10 без цены:")
for r in empty[:10]:
    print(f"  {r['offer_id']:<25} {r['name'][:50]}")