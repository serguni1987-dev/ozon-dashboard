"""
check_prices.py
Полная структура /v5/product/info/prices для 3 SKU из топ-3 по выручке.
"""
import os, json, sqlite3, requests
from dotenv import load_dotenv

load_dotenv()
CID, KEY = os.getenv("OZON_CLIENT_ID"), os.getenv("OZON_API_KEY")
BASE = os.getenv("OZON_BASE_URL", "https://api-seller.ozon.ru")
H = {"Client-Id": CID, "Api-Key": KEY, "Content-Type": "application/json"}

# Топ-3 SKU по выручке
conn = sqlite3.connect("ozon.db")
cur = conn.execute("""
    SELECT p.offer_id, p.sku, p.name, SUM(s.revenue) as rev
    FROM sales_daily s
    JOIN products p ON p.sku = s.sku
    WHERE p.is_own = 1
    GROUP BY s.sku
    ORDER BY rev DESC
    LIMIT 3
""")
top = cur.fetchall()
conn.close()

offer_ids = [r[0] for r in top]

print("Топ-3 SKU по выручке:")
for oid, sku, name, rev in top:
    print(f"  {oid} (SKU {sku}) — {rev:.0f} ₽ — {name[:50]}")
print()

# Запрос по offer_id
r = requests.post(BASE + "/v5/product/info/prices", headers=H, json={
    "filter": {"offer_id": offer_ids, "visibility": "ALL"},
    "limit": 10,
}, timeout=30)

print(f"Статус: {r.status_code}")
if r.status_code != 200:
    print(r.text[:500])
    exit()

data = r.json()
print(f"Получено: {len(data.get('items', []))} товаров\n")

for item in data.get("items", []):
    print("=" * 70)
    print(f"Offer ID: {item.get('offer_id')}")
    print(f"Product ID: {item.get('product_id')}")
    print("=" * 70)
    print(json.dumps(item, ensure_ascii=False, indent=2))
    print()