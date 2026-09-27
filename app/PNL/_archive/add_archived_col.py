import sqlite3
con = sqlite3.connect("ozon.db")
cols = [r[1] for r in con.execute("PRAGMA table_info(products)")]
if "is_archived" not in cols:
    con.execute("ALTER TABLE products ADD COLUMN is_archived INTEGER DEFAULT 0")
    con.commit()
    print("[OK] Колонка is_archived добавлена")
else:
    print("[i] Колонка is_archived уже есть")
con.close()
