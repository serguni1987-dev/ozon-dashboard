import sqlite3
con = sqlite3.connect("ozon.db")
n1 = con.execute("DELETE FROM monthly_realization_rows WHERE month != '2026-08'").rowcount
n2 = con.execute("DELETE FROM monthly_reports WHERE month != '2026-08'").rowcount
con.commit()
con.close()
print(f"[OK] Удалено: rows={n1}, reports={n2}")
