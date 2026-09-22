"""
check_payouts.py — ищем метод с историей выплат.
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

date_to = datetime.now().strftime("%Y-%m-%dT23:59:59Z")
date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00Z")

print("=" * 80)
print("ПОИСК МЕТОДА С ИСТОРИЕЙ ВЫПЛАТ")
print("=" * 80)
print(f"Период: {date_from} — {date_to}\n")

# Вариант 1: cash-flow-statement/list с RFC3339
print("[1] /v1/finance/cash-flow-statement/list")
r = requests.post(
    "https://api-seller.ozon.ru/v1/finance/cash-flow-statement/list",
    headers=H,
    json={"date": {"from": date_from, "to": date_to}, "page": 1, "page_size": 10},
    timeout=60,
)
print(f"    HTTP: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    print(json.dumps(data, ensure_ascii=False, indent=2)[:2000])
else:
    print(f"    {r.text[:400]}")

# Вариант 2: balance с детализацией payments
print("\n[2] /v1/finance/balance — детализация payments")
r2 = requests.post(
    "https://api-seller.ozon.ru/v1/finance/balance",
    headers=H,
    json={"date_from": "2026-08-21", "date_to": "2026-09-20"},
    timeout=60,
)
if r2.status_code == 200:
    data2 = r2.json()
    payments = (data2.get("total") or {}).get("payments") or []
    print(f"    payments: {json.dumps(payments, ensure_ascii=False, indent=2)[:1500]}")
else:
    print(f"    {r2.text[:300]}")

print("\n" + "=" * 80)
