import sqlite3
con = sqlite3.connect("ozon.db")
n = con.execute("DELETE FROM price_changes WHERE api_status = 'error'").rowcount
con.commit()
con.close()
print(f"[OK] Удалено ошибочных записей: {n}")
