import sqlite3
con = sqlite3.connect("ozon.db")
con.row_factory = sqlite3.Row

# Найти дубликаты (одинаковый offer_id + category + action_text)
rows = con.execute("""
    SELECT id, offer_id, action_text, created_at, note
    FROM decisions ORDER BY id
""").fetchall()

seen = {}
to_delete = []
for r in rows:
    key = (r["offer_id"], r["action_text"])
    if key in seen:
        to_delete.append(r["id"])
    else:
        seen[key] = r["id"]

if to_delete:
    con.executemany("DELETE FROM decisions WHERE id = ?", [(i,) for i in to_delete])
    con.commit()
    print(f"[OK] Удалены дубликаты: {to_delete}")
else:
    print("[i] Дубликатов нет")

# Показать, что осталось
print("\nОсталось решений:")
for r in con.execute("SELECT id, offer_id, action_text, created_at FROM decisions ORDER BY id"):
    print(f"  #{r['id']}  {r['offer_id']:<18} {r['action_text'][:50]}  ({r['created_at'][:16]})")

con.close()
