import os, json, requests
from dotenv import load_dotenv
load_dotenv()
H = {"Client-Id": os.getenv("OZON_CLIENT_ID"), "Api-Key": os.getenv("OZON_API_KEY"), "Content-Type": "application/json"}
r = requests.post("https://api-seller.ozon.ru/v1/finance/accrual/by-day", headers=H, json={"date": "2026-09-01", "last_id": ""}, timeout=60)
data = r.json()
for acc in data.get("accruals", []):
    for p in (acc.get("posting") or {}).get("products") or []:
        if p.get("commission"):
            print(json.dumps(p["commission"], ensure_ascii=False, indent=2))
            break
    else:
        continue
    break
