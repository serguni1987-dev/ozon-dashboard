import sqlite3
con = sqlite3.connect("ozon.db")

from sheets_sync import build_capital
data = build_capital(con)

print("Всего строк в data:", len(data))
print()
print("Строки 10-14 (после title, subtitle, пусто):")
for i, row in enumerate(data[9:14], 10):
    a = row[0] if len(row) > 0 else ""
    b = row[1] if len(row) > 1 else ""
    c = row[2] if len(row) > 2 else ""
    print(f"  Строка {i}: A={a!r:<35} B={b!r:<15} C={c!r}")

con.close()
