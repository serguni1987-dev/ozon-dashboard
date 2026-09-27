import os, json, requests
from dotenv import load_dotenv
load_dotenv()
H = {"Client-Id": os.getenv("OZON_CLIENT_ID"),
     "Api-Key": os.getenv("OZON_API_KEY"),
     "Content-Type": "application/json"}

r = requests.post(
    "https://api-seller.ozon.ru/v4/product/info/stocks",
    headers=H,
    json={"filter": {"visibility": "ALL"}, "last_id": "", "limit": 1000},
    timeout=60,
)
data = r.json()
print("Ключи ответа:", list(data.keys()))
print("last_id:", data.get("last_id"))
print("items:", len(data.get("items") or []))
# Первый и последний item
items = data.get("items") or []
if items:
    print("\nПервый item (ключи):", list(items[0].keys()))
    print("Последний item (offer_id):", items[-1].get("offer_id"))
