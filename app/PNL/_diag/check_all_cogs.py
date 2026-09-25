import csv
rows = list(csv.reader(open("pnl_2026.csv", encoding="utf-8-sig"), delimiter=";"))
hdr = rows[1]

OZON = {
    "янв": 147966, "фев": 104799, "мар": 44239,
    "апр": 28084, "май": 30861,
    "июн": 6302,
    "авг": 112905,
}

print(f"{'Мес':<5} | {'Ozon':>10} | {'Наше':>11} | {'Δ':>10} | {'Δ%':>6}")
print("-" * 55)
for m, oz in OZON.items():
    idx = hdr.index(m)
    for r in rows:
        if r and r[0].strip() == "Себестоимость с учётом возвратов":
            v = r[idx] if len(r) > idx else "0"
            try:
                our = abs(float(v.replace(" ", "").replace(",", ".")))
            except ValueError:
                our = 0
            diff = our - oz
            pct = (diff / oz * 100) if oz else 0
            mark = "⚠" if abs(pct) > 5 else "✓"
            print(f"{m:<5} | {oz:>10,.0f} | {our:>11,.0f} | {diff:>+10,.0f} | {pct:>+5.1f}% {mark}")
            break