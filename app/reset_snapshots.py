import sqlite3
con = sqlite3.connect("ozon.db")
n = con.execute("DELETE FROM dashboard_snapshots").rowcount
con.commit()
con.close()
print(f"[OK] Удалено снапшотов: {n}. Следующий запуск создаст корректный.")
