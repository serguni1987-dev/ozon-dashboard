import json

with open("peek_august_raw.json", encoding="utf-8") as f:
    d = json.load(f)
rows = d["result"]["rows"]

def agg(container, field):
    total = 0.0
    for r in rows:
        c = r.get(container) or {}
        v = c.get(field, 0) or 0
        if isinstance(v, (int, float)):
            total += v
    return total

print("── delivery_commission ──")
for fld in ("price_per_instance", "quantity", "amount", "compensation",
            "commission", "bonus", "standard_fee", "total", "stars",
            "bank_coinvestment", "pick_up_point_coinvestment"):
    print(f"  {fld:30} {agg('delivery_commission', fld):>18,.2f}")

print()
print("── return_commission ──")
for fld in ("price_per_instance", "quantity", "amount", "compensation",
            "commission", "bonus", "standard_fee", "total", "stars"):
    print(f"  {fld:30} {agg('return_commission', fld):>18,.2f}")

print()
print("── Пример одной строки (row[0]) ──")
print(json.dumps(rows[0], ensure_ascii=False, indent=2))