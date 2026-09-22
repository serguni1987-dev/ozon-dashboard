import requests, os, json
from dotenv import load_dotenv
load_dotenv()
H = {"Client-Id": os.getenv("OZON_CLIENT_ID"),
     "Api-Key": os.getenv("OZON_API_KEY"),
     "Content-Type": "application/json"}

targets = ["CDKR08615714025","FBR007E5716025","OBKR0261579020","SM001200220",
           "SM002150210","CDKR0631579025","FBR009E5714025","OBKR0261578016025",
           "OBR149E5718025","CDKR06615712025","CDKR06615716025","FB007E57",
           "FBR003E5716025","FBR007E5714025","FBR015E5716025",
           "OBKR0271578016025","OBR144E5716025"]

r = requests.post("https://api-seller.ozon.ru/v3/product/info/list",
                  headers=H,
                  json={"offer_id": targets},
                  timeout=60)
print("HTTP:", r.status_code)
data = r.json()
items = data.get("items") or data.get("result") or []
if isinstance(items, dict):
    items = items.get("items") or []
print(f"Найдено: {len(items)}")
for it in items:
    print(json.dumps(it, ensure_ascii=False)[:400])
