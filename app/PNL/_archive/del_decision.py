import sqlite3
con = sqlite3.connect("ozon.db")
con.execute("DELETE FROM decisions WHERE id = 1")
con.commit()
con.close()
print("[OK] Битая запись удалена")
