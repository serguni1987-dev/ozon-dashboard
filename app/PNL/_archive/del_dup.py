import sqlite3
con = sqlite3.connect("ozon.db")
con.execute("DELETE FROM decisions WHERE id = 3")
con.commit()
print("Удалено решение #3 (дубликат)")
for r in con.execute("SELECT id, offer_id, action_text FROM decisions"):
    print(f"  #{r[0]}  {r[1]}  {r[2]}")
con.close()
