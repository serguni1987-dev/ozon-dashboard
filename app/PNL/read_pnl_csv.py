import csv
import os

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(APP_DIR, "pnl_2026.csv")

with open(CSV, encoding="utf-8-sig", newline="") as f:
    rows = list(csv.reader(f, delimiter=";"))

# Заголовки (строка 2)
print("Заголовки:", rows[1][:16])
print()

# Ключевые строки
keys = ["ДОХОДЫ", "Прямые (переменные) расходы (всего)", "Себестоимость с учётом возвратов", 
        "ВАЛОВАЯ ПРИБЫЛЬ", "Налоги (УСН 15%)", "ЧИСТАЯ ПРИБЫЛЬ"]

for row in rows:
    if row and row[0] in keys:
        print(f"\n{row[0]}:")
        # Колонки C-N = янв-дек (индексы 2-13)
        for i, m in enumerate(["янв","фев","мар","апр","май","июн","июл","авг","сен","окт","ноя","дек"]):
            val = row[2+i] if len(row) > 2+i else ""
            if val and val != "0":
                print(f"    {m}: {val}")
