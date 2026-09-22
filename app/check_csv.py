import csv
with open("costs_template.csv", encoding="utf-8-sig") as f:
    rows = list(csv.reader(f, delimiter=";"))
print(f"Строк в CSV: {len(rows)}")
print(f"Заголовок:   {rows[0]}")
print(f"\nПервые 5 строк:")
for r in rows[1:6]:
    print(" ", r)
print(f"\nПоследние 5 строк:")
for r in rows[-5:]:
    print(" ", r)

# Ищем наши 10 SKU
targets = ["OVL0492402602","OVL0312402602","OVS0032402602","VLR007E414025",
           "OCPR008E420020","VL007E4","OCPR0132416030","OCE017E4",
           "OCPR009E416030","OCPR002E418030"]
found = [r for r in rows[1:] if r and r[0] in targets]
print(f"\nИз 10 целевых SKU найдено в CSV: {len(found)}")
for r in found:
    print(" ", r)
