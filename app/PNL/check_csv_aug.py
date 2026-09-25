import csv

with open("pnl_2026.csv", encoding="utf-8-sig", newline="") as f:
    rows = list(csv.reader(f, delimiter=";"))

# Заголовок — строка 2 (индекс 1), смотрим что в колонке "авг"
header = rows[1] if len(rows) > 1 else []
try:
    idx_aug = header.index("авг")
except ValueError:
    idx_aug = 9  # fallback
print(f"Колонка 'авг' — индекс {idx_aug}")
print()
print(f"{'#':>3} | {'Строка':<40} | {'авг':>14}")
print("-" * 65)

for i, r in enumerate(rows, start=1):
    if i < 14 or i > 28:
        continue
    label = r[0][:40] if r else ""
    val = r[idx_aug] if len(r) > idx_aug else ""
    print(f"{i:>3} | {label:<40} | {val:>14}")

# Итоговая проверка: J16 = J17+J18+J19+J20
def to_f(s):
    try:
        return float(s.replace(" ", "").replace("\xa0", "").replace(",", "."))
    except Exception:
        return 0.0

row16 = to_f(rows[15][idx_aug]) if len(rows) > 15 else 0
row17 = to_f(rows[16][idx_aug]) if len(rows) > 16 else 0
row18 = to_f(rows[17][idx_aug]) if len(rows) > 17 else 0
row19 = to_f(rows[18][idx_aug]) if len(rows) > 18 else 0
row20 = to_f(rows[19][idx_aug]) if len(rows) > 19 else 0

print()
print("── Проверка: J16 = J17+J18+J19+J20 ─────────────")
print(f"  J16              = {row16:>12.2f}")
print(f"  J17+J18+J19+J20  = {row17+row18+row19+row20:>12.2f}")
print(f"  разница          = {row16-(row17+row18+row19+row20):>12.2f}")

# То же для 21 = 22+23
row21 = to_f(rows[20][idx_aug]) if len(rows) > 20 else 0
row22 = to_f(rows[21][idx_aug]) if len(rows) > 21 else 0
row23 = to_f(rows[22][idx_aug]) if len(rows) > 22 else 0
print()
print("── Проверка: J21 = J22+J23 ─────────────────────")
print(f"  J21              = {row21:>12.2f}")
print(f"  J22+J23          = {row22+row23:>12.2f}")
print(f"  разница          = {row21-(row22+row23):>12.2f}")