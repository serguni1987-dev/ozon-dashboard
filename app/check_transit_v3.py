"""
check_transit_v3.py - финальная проверка методов на данные о товарах в пути.
"""
import os
import json
import time
import sqlite3
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

H = {
    "Client-Id": os.getenv("OZON_CLIENT_ID"),
    "Api-Key": os.getenv("OZON_API_KEY"),
    "Content-Type": "application/json",
}
DB = "ozon.db"


def show(name, url, body):
    print()
    print("=" * 70)
    print(f"[{name}]")
    print("=" * 70)
    try:
        r = requests.post(url, headers=H, json=body, timeout=60)
        print(f"HTTP: {r.status_code}")
        if r.status_code != 200:
            print(f"Ошибка: {r.text[:600]}")
            return None
        data = r.json()
        print(json.dumps(data, ensure_ascii=False, indent=2)[:4000])
        return data
    except Exception as e:
        print(f"Исключение: {e}")
        return None


def main():
    # Собираем SKU с остатками из нашей БД (макс 100)
    con = sqlite3.connect(DB)
    rows = con.execute("""
        SELECT cp.sku FROM current_prices cp
        JOIN products p ON p.offer_id = cp.offer_id
        WHERE p.is_own = 1 AND p.is_archived = 0
        LIMIT 100
    """).fetchall()
    skus = [r[0] for r in rows if r[0]]
    con.close()
    print(f"SKU для запроса: {len(skus)}")
    print(f"Первые 5: {skus[:5]}")

    # === 1. v1/analytics/stocks с SKU ===
    print("\nЖдём 5 сек (после прошлого 429)...")
    time.sleep(5)

    date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00Z")
    date_to = datetime.now().strftime("%Y-%m-%dT23:59:59Z")

    show(
        "v1/analytics/stocks (с SKU)",
        "https://api-seller.ozon.ru/v1/analytics/stocks",
        {
            "skus": skus[:100],
            "date_from": date_from,
            "date_to": date_to,
            "limit": 100,
            "cursor": "",
        },
    )

    # === 2. v3/supply-order/list с правильным sort_by ===
    time.sleep(1)
    show(
        "v3/supply-order/list (IN_TRANSIT)",
        "https://api-seller.ozon.ru/v3/supply-order/list",
        {
            "filter": {"states": ["IN_TRANSIT"]},
            "limit": 20,
            "sort_by": "ORDER_STATE_UPDATED_AT",
            "sort_dir": "DESC",
        },
    )


if __name__ == "__main__":
    main()
