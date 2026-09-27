import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

H = {
    "Client-Id": os.getenv("OZON_CLIENT_ID"),
    "Api-Key": os.getenv("OZON_API_KEY"),
    "Content-Type": "application/json",
}

r = requests.post(
    "https://api-seller.ozon.ru/v5/product/info/prices",
    headers=H,
    json={"filter": {"visibility": "ALL"}, "cursor": "", "limit": 3},
    timeout=60,
)

data = r.json()
items = data.get("items") or []
print("Получено:", len(items))
print()
if items:
    print("Сырой ответ первого товара:")
    print(json.dumps(items[0], ensure_ascii=False, indent=2))
else:
    print("Ответ:", json.dumps(data, ensure_ascii=False, indent=2)[:2000])
