import sqlite3
con = sqlite3.connect("ozon.db")

# Импортируем build_money и смотрим, что она возвращает
import sys
sys.path.insert(0, ".")
from sheets_sync import build_money

data = build_money(con)
print(f"Всего строк: {len(data)}")
print()
for i, row in enumerate(data[14:24], 15):
    first = row[0] if row else ""
    second = row[1] if len(row) > 1 else ""
    print(f"  {i:>3}: A={first[:30]!r:<35} B={second[:50]!r}")
con.close()
