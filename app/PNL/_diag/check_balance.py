"""
check_balance.py — проверяет доступность /v1/finance/balance.
"""
import os
import json
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

H = {
    "Client-Id": os.getenv("OZON_CLIENT_ID"),
    "Api-Key": os.getenv("OZON_API_KEY"),
    "Content-Type": "application/json",
}

# Период — последние 30 дней
date_to = datetime.now().strftime("%Y-%m-%d")
date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

print("=" * 70)
print("ПРОВЕРКА /v1/finance/balance")
print("=" * 70)
print(f"\nПериод: {date_from} — {date_to}\n")

# 1. Баланс
print("[1] POST /v1/finance/balance")
r = requests.post(
    "https://api-seller.ozon.ru/v1/finance/balance",
    headers=H,
    json={"date_from": date_from, "date_to": date_to},
    timeout=60,
)
print(f"    HTTP: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    print(f"    Ответ:")
    print(json.dumps(data, ensure_ascii=False, indent=2)[:2000])
else:
    print(f"    Ошибка: {r.text[:500]}")

# 2. Cash-flow statement
print("\n[2] POST /v1/finance/cash-flow-statement/list")
r2 = requests.post(
    "https://api-seller.ozon.ru/v1/finance/cash-flow-statement/list",
    headers=H,
    json={"date": {"from": date_from, "to": date_to}, "page": 1, "page_size": 10},
    timeout=60,
)
print(f"    HTTP: {r2.status_code}")
if r2.status_code == 200:
    data2 = r2.json()
    print(f"    Ответ:")
    print(json.dumps(data2, ensure_ascii=False, indent=2)[:2000])
else:
    print(f"    Ошибка: {r2.text[:500]}")

print("\n" + "=" * 70)
