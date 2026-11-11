import sqlite3
from unitka import config
con = sqlite3.connect(str(config.DB_PATH))
cur = con.cursor()

skus = [1610775365, 1288892888, 1609492909, 1609833125, 1605108599]

print(f"{'Артикул':<20} | {'Себестоимость':>15} | {'Цена в базе':>15}")
print("-" * 55)
for sku in skus:
    # Ищем offer_id и себестоимость
    r = cur.execute("SELECT offer_id FROM sku_map WHERE ozon_sku = ?", (sku,)).fetchone()
    offer = r[0] if r else "?"
    
    c = cur.execute("SELECT cost_price FROM product_cost_history WHERE sku = ? ORDER BY date_from DESC LIMIT 1", (sku,)).fetchone()
    cost = c[0] if c else 0
    
    print(f"{offer:<20} | {cost:>15,.2f} | {cost*2.5:>15,.2f} (примерно, для проверки)")
con.close()