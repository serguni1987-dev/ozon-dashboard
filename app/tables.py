import sqlite3

con = sqlite3.connect("ozon.db")

print("=== Все таблицы ===")
tables = [r[0] for r in con.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
)]
for t in tables:
    print(f"  {t}")

print()
print("=== Структуры ключевых таблиц ===")
for t in ("sales_daily", "orders", "postings", "returns",
          "stocks", "fbo_stocks", "fbs_stocks",
          "product_info", "products"):
    try:
        cols = [r[1] for r in con.execute(f"PRAGMA table_info({t})")]
        if cols:
            print(f"\n[{t}]")
            for c in cols:
                print(f"  {c}")
    except sqlite3.Error:
        pass