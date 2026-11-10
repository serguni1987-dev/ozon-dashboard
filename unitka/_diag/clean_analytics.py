import sqlite3
from unitka import config
con = sqlite3.connect(str(config.DB_PATH))
cur = con.cursor()

print("=== Чистка analytics_manual ===")
before = cur.execute("SELECT COUNT(DISTINCT sku) FROM analytics_manual").fetchone()[0]
print(f"SKU до чистки: {before}")

cur.execute("""
    DELETE FROM analytics_manual
    WHERE sku NOT IN (SELECT DISTINCT CAST(sku AS INTEGER) FROM postings_daily WHERE sku IS NOT NULL)
""")
con.commit()

after = cur.execute("SELECT COUNT(DISTINCT sku) FROM analytics_manual").fetchone()[0]
print(f"SKU после чистки: {after}")

cur.execute("SELECT MAX(date), COUNT(*) FROM analytics_manual")
r = cur.fetchone()
print(f"Макс. дата: {r[0]} | строк: {r[1]}")
con.close()