import csv
path = r"C:\Users\sergu\Desktop\проект\out.xlsx"   # это на самом деле CSV
with open(path, "r", encoding="utf-8-sig", newline="") as f:
    r = csv.reader(f, delimiter=";", quotechar='"')
    header = next(r)
print(f"Всего колонок: {len(header)}")
for i, h in enumerate(header, 1):
    print(f"  {i:>2}. {h}")