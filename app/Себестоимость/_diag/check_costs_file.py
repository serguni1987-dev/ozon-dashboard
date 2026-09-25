"""check_costs_file.py — что в costs_all.csv, есть ли там 16 SKU."""
import csv

CSV = r"C:\Users\sergu\Desktop\проект\Себестоимость\costs_all.csv"

# Пробуем разные кодировки
for enc in ("utf-8-sig", "utf-8", "cp1251"):
    try:
        with open(CSV, encoding=enc, newline="") as f:
            rows = list(csv.reader(f, delimiter="\t"))
        print(f"[OK] Кодировка: {enc}")
        print(f"     Строк: {len(rows)}")
        break
    except Exception as e:
        print(f"[!] {enc}: {e}")

header = rows[0]
print(f"\nКолонки: {header}")
print(f"\nПервые 3 строки:")
for r in rows[1:4]:
    print(f"  {r}")

# Индексы колонок
col_sku = header.index("SKU") if "SKU" in header else 1
col_offer = header.index("Артикул") if "Артикул" in header else 0
col_cost = header.index("Себестоимость") if "Себестоимость" in header else 4

# Собираем все SKU из файла
skus_in_file = set()
for r in rows[1:]:
    if len(r) > col_sku:
        try:
            skus_in_file.add(int(r[col_sku]))
        except (ValueError, IndexError):
            pass
print(f"\nSKU в файле: {len(skus_in_file)}")

# Наши 16
missing_16 = [1879636339, 1281819166, 2288681486, 1591552350, 1609915178,
              2288693078, 1281720312, 1879635959, 1879635938, 1598572996,
              1879636428, 1267412652, 1616350111, 1331069847, 1610041376, 1609915213]

print(f"\n=== Проверка 16 SKU в costs_all.csv ===")
found = 0
for sku in missing_16:
    match = [r for r in rows[1:] if len(r) > col_sku and r[col_sku].strip() == str(sku)]
    if match:
        found += 1
        r = match[0]
        cost = r[col_cost] if len(r) > col_cost else "?"
        print(f"  {sku:>12} ✓  {r[col_offer]:<25} cost={cost}")
    else:
        print(f"  {sku:>12} ✗  НЕ НАЙДЕН в файле")

print(f"\nНайдено в файле: {found} из {len(missing_16)}")