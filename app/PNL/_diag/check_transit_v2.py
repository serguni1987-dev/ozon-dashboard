"""
check_transit_v2.py — исправленная проверка.
"""
import os
import json
import time
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

H = {
    "Client-Id": os.getenv("OZON_CLIENT_ID"),
    "Api-Key": os.getenv("OZON_API_KEY"),
    "Content-Type": "application/json",
}


def show(name, url, body):
    print()
    print("=" * 70)
    print(f"[{name}]")
    print("=" * 70)
    try:
        r = requests.post(url, headers=H, json=body, timeout=60)
        print(f"HTTP: {r.status_code}")
        if r.status_code != 200:
            print(f"Ошибка: {r.text[:500]}")
            return
        data = r.json()
        print(json.dumps(data, ensure_ascii=False, indent=2)[:3000])
    except Exception as e:
        print(f"Исключение: {e}")


def main():
    # === 1. v1/analytics/stocks — с паузой после прошлого 429 ===
    print("Ждём 5 секунд после rate limit...")
    time.sleep(5)

    date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00Z")
    date_to = datetime.now().strftime("%Y-%m-%dT23:59:59Z")

    show(
        "v1/analytics/stocks (новый метод)",
        "https://api-seller.ozon.ru/v1/analytics/stocks",
        {"date_from": date_from, "date_to": date_to, "limit": 5, "cursor": ""},
    )

    # === 2. v2/analytics/stock_on_warehouses — с фильтром по типу ===
    time.sleep(1)
    show(
        "v2/analytics/stock_on_warehouses (FBO)",
        "https://api-seller.ozon.ru/v2/analytics/stock_on_warehouses",
        {"limit": 5, "warehouse_type": "FBO"},
    )

    # === 3. v3/supply-order/list — с sort_by ===
    time.sleep(1)
    show(
        "v3/supply-order/list (заявки на поставку)",
        "https://api-seller.ozon.ru/v3/supply-order/list",
        {
            "filter": {"states": ["IN_TRANSIT", "DATA_FILLING", "READY_TO_SUPPLY"]},
            "limit": 10,
            "sort_by": "CREATE_DATE_DESC",
        },
    )


if __name__ == "__main__":
    main()
