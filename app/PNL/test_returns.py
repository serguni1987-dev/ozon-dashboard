import json

with open("peek_august_raw.json", encoding="utf-8") as f:
    d = json.load(f)
rows = d["result"]["rows"]

n_returns = 0
sum_dc = 0.0
sum_rc = 0.0

for i, r in enumerate(rows):
    dc = r.get("delivery_commission") or {}
    rc = r.get("return_commission") or {}
    dc_amount = float(dc.get("amount") or 0)
    rc_amount = float(rc.get("amount") or 0)
    if rc:
        n_returns += 1
        print(f"Row {i}: dc={dc_amount:.2f}  rc={rc_amount:.2f}  net={dc_amount - rc_amount:.2f}")
    sum_dc += dc_amount
    sum_rc += rc_amount

print()
print(f"Всего строк: {len(rows)}")
print(f"Строк с возвратом: {n_returns}")
print(f"Сумма dc_amount: {sum_dc:,.2f}")
print(f"Сумма rc_amount: {sum_rc:,.2f}")
print(f"Разница: {sum_dc - sum_rc:,.2f}")