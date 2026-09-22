import csv
with open("costs_all.csv", encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f, delimiter=";"))
filled = [r for r in rows if (r.get("cost_price") or "").strip() not in ("", "0", "-")]
print(f"Всего строк: {len(rows)}")
print(f"С заполненной себестоимостью: {len(filled)}")
for r in filled[:5]:
    print(" ", r["offer_id"], "→", r["cost_price"])
