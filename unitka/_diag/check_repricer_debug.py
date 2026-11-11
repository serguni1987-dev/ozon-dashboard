from unitka.auto_repricer import get_sku_data, get_real_prices
from unitka.ozon_client import OzonClient
from unitka.db import connect

conn = connect()
cur = conn.cursor()
skus = get_sku_data(cur)
client = OzonClient()
offer_ids = [s["offer_id"] for s in skus]
real_prices = get_real_prices(client, offer_ids)

print(f"{'Артикул':<15} | {'Реальная цена':>12} | {'Наша мин (x1.15)':>15} | {'Себестоимость':>12}")
print("-" * 65)
for s in skus:
    offer = s["offer_id"]
    real = real_prices.get(offer, 0)
    min_naive = s["min_price"]
    cost = s["cost"]
    print(f"{offer:<15} | {real:>12,.0f} | {min_naive:>15,.0f} | {cost:>12,.0f}")
conn.close()