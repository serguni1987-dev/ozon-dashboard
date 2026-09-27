import sqlite3
con = sqlite3.connect("ozon.db")
cols = [r[1] for r in con.execute("PRAGMA table_info(products)")]
print("Колонки products:", cols)
if "cost_date" in cols:
    n = con.execute("SELECT COUNT(*) FROM products WHERE is_own=1 AND cost_date IS NOT NULL").fetchone()[0]
    print(f"С cost_date: {n}")
else:
    con.execute("ALTER TABLE products ADD COLUMN cost_date TEXT")
    con.execute("UPDATE products SET cost_date = '2026-09-24' WHERE is_own=1 AND cost_price > 0")
    con.commit()
    print("[OK] Колонка cost_date добавлена и заполнена")
con.close()
