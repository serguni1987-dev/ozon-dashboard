import csv
rows = list(csv.reader(open("pnl_2026.csv", encoding="utf-8-sig"), delimiter=";"))
hdr = rows[1]
i1 = hdr.index("янв")
print(f"{'#':>3} | {'Строка':<42} | {'янв':>14}")
print("-" * 68)
for i, r in enumerate(rows, start=1):
    if i < 8 or i > 47:
        continue
    label = r[0][:42] if r else ""
    val = r[i1] if len(r) > i1 else ""
    print(f"{i:>3} | {label:<42} | {val:>14}")