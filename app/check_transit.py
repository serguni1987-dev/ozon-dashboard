"""
check_transit.py - проверяет методы API на данные о товарах в пути.
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


def show(name, url, body):
    print()
    print("=" * 70)
    print(f"[ПРОВЕРКА] {name}")
    print("=" * 70)
    try:
        r = requests.post(url, headers=H, json=body, timeout=60)
        print(f"HTTP: {r.status_code}")
        if r.status_code != 200:
            print(f"Ошибка: {r.text[:400]}")
            return
        data = r.json()
        # Ищем первый список в ответе
        for key in ["items", "result", "stocks", "rows", "warehouses"]:
            if key in data and isinstance(data[key], list) and data[key]:
                print(f"Пример элемента из '{key}':")
                print(json.dumps(data[key][0], ensure_ascii=False, indent=2)[:2000])
                return
        # Если нет списка - показываем корень
        print(json.dumps(data, ensure_ascii=False, indent=2)[:2000])
    except Exception as e:
        print(f"Исключение: {e}")


def main():
    # 1. Отчёт по остаткам на складах и в пути
    show(
        "v2/analytics/stock_on_warehouses",
        "https://api-seller.ozon.ru/v2/analytics/stock_on_warehouses",
        {"limit": 5},
    )

    # 2. Новый метод аналитики остатков
    date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00Z")
    date_to = datetime.now().strftime("%Y-%m-%dT23:59:59Z")
    show(
        "v1/analytics/stocks",
        "https://api-seller.ozon.ru/v1/analytics/stocks",
        {"date_from": date_from, "date_to": date_to, "limit": 5, "cursor": ""},
    )

    # 3. Заявки на поставку FBO (в пути)
    show(
        "v3/supply-order/list",
        "https://api-seller.ozon.ru/v3/supply-order/list",
        {"filter": {"states": ["IN_TRANSIT"]}, "limit": 5},
    )


if __name__ == "__main__":
    main()
