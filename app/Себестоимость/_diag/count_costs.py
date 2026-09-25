import csv
with open("costs_all.csv", encoding="utf-8-sig", newline="") as f:
    rows = list(csv.reader(f, delimiter=";"))
print(f"Всего строк: {len(rows)}")
print(f"С непустым cost_price: {sum(1 for r in rows[1:] if len(r) > 6 and r[6].strip())}")
print(f"С непустым offer_id: {sum(1 for r in rows[1:] if len(r) > 0 and r[0].strip())}")
print()
print("Первые 5 строк после заголовка:")
for r in rows[1:6]:
    print(f"  {r[:3]}...{r[6:8]}")