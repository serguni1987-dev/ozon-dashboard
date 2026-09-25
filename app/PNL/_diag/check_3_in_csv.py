import csv

with open("costs_all.csv", encoding="utf-8-sig", newline="") as f:
    rows = list(csv.reader(f, delimiter=";"))

header = rows[0]
print(f"Колонки: {header}")
idx_offer = header.index("offer_id")
idx_cost = header.index("cost_price")

targets = ("OBKR0241579020", "OBKR0251578016025", "MS01324")
print(f"\nЭти 3 SKU в costs_all.csv:")
for r in rows[1:]:
    if len(r) > idx_offer and r[idx_offer].strip() in targets:
        print(f"  {r}")