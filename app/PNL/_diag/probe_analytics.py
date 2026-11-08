import os, requests, json
from dotenv import load_dotenv

load_dotenv(r'C:\Users\sergu\Desktop\проект\app\.env')
H = {
    'Client-Id': os.getenv('OZON_CLIENT_ID'),
    'Api-Key':   os.getenv('OZON_API_KEY'),
    'Content-Type': 'application/json',
}

body = {
    'date_from': '2026-01-01',
    'date_to':   '2026-10-10',
    'metrics':   ['ordered_units', 'delivered_units', 'returns', 'cancellations'],
    'dimensions': ['month'],
    'limit':      100,
    'offset':     0,
}

r = requests.post('https://api-seller.ozon.ru/v1/analytics/data',
                  headers=H, json=body, timeout=60)
print('HTTP', r.status_code)
j = r.json()
print(json.dumps(j, ensure_ascii=False, indent=2))