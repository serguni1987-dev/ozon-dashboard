import sqlite3
con = sqlite3.connect("ozon.db")
print("=== current_stocks ===")
for r in con.execute("PRAGMA table_info(current_stocks)"):
    print(r)
print()
print("=== 5 строк ===")
for r in con.execute("SELECT * FROM current_stocks LIMIT 5"):
    print(r)