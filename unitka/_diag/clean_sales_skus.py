import sqlite3
from unitka import config
con = sqlite3.connect(str(config.DB_PATH))
cur = con.cursor()

print("=== Фильтрация SKU в sales_daily ===")
before = cur.execute("SELECT COUNT(DISTINCT sku) FROM sales_daily").fetchone()[0]
print(f"Уникальных SKU до чистки: {before}")

# Удаляем из sales_daily все SKU, которых нет в postings_daily
cur.execute("""
    DELETE FROM sales_daily
    WHERE sku NOT IN (SELECT DISTINCT CAST(sku AS INTEGER) FROM postings_daily WHERE sku IS NOT NULL)
""")
con.commit()

after = cur.execute("SELECT COUNT(DISTINCT sku) FROM sales_daily").fetchone()[0]
print(f"Уникальных SKU после чистки: {after}")

print("\n=== Проверка ===")
cur.execute("SELECT SUM(revenue) FROM sales_daily")
total_rev = cur.fetchone()[0]
print(f"Общая выручка в sales_daily (только ваши SKU): {total_rev:,.2f} ₽")
con.close()