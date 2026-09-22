"""
map_metrics.py
Точный маппинг: посылаем по 1 метрике за раз, смотрим что возвращается.
"""
import os
import json
import time
import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("OZON_CLIENT_ID")
API_KEY = os.getenv("OZON_API_KEY")
BASE_URL = os.getenv("OZON_BASE_URL", "https://api-seller.ozon.ru")

HEADERS = {
    "Client-Id": CLIENT_ID,
    "Api-Key": API_KEY,
    "Content-Type": "application/json",
}

WORKING_METRICS = [
    "revenue", "ordered_units", "hits_view_search", "hits_view_pdp", "hits_view",
    "hits_tocart_search", "hits_tocart_pdp", "hits_tocart", "session_view_search",
    "session_view_pdp", "session_view", "conv_tocart_search", "conv_tocart_pdp",
    "conv_tocart",
]


def query_one_metric(metric):
    payload = {
        "date_from": "2026-08-01",
        "date_to": "2026-08-02",
        "metrics": [metric],
        "dimension": ["day", "sku"],
        "limit": 3,
        "offset": 0,
    }
    r = requests.post(BASE_URL + "/v1/analytics/data", headers=HEADERS, json=payload, timeout=20)
    return r


def main():
    print(f"Проверяем {len(WORKING_METRICS)} метрик по одной\n")
    print(f"{'Метрика':<30} {'Статус':<8} {'Значения (первые 3 строки)'}")
    print("-" * 90)

    for metric in WORKING_METRICS:
        r = query_one_metric(metric)
        if r.status_code != 200:
            print(f"{metric:<30} {r.status_code:<8} ERROR: {r.text[:60]}")
            time.sleep(0.3)
            continue

        data = r.json()
        rows = data.get("result", {}).get("data", [])
        values = []
        for row in rows[:3]:
            m = row.get("metrics", [])
            values.append(m[0] if m else None)
        print(f"{metric:<30} {r.status_code:<8} {values}")
        time.sleep(0.3)

    # Теперь пошлём 3 метрики вместе и посмотрим, как они лягут
    print("\n=== Контрольный тест: 3 метрики вместе ===")
    payload = {
        "date_from": "2026-08-01",
        "date_to": "2026-08-02",
        "metrics": ["revenue", "ordered_units", "hits_view"],
        "dimension": ["day", "sku"],
        "limit": 3,
        "offset": 0,
    }
    r = requests.post(BASE_URL + "/v1/analytics/data", headers=HEADERS, json=payload, timeout=20)
    print(f"Статус: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        rows = data.get("result", {}).get("data", [])
        for row in rows[:3]:
            dim = row.get("dimensions", [])
            print(f"  Дата: {dim[0].get('id') if dim else '?'}, "
                  f"SKU: {dim[1].get('id') if len(dim) > 1 else '?'}, "
                  f"metrics = {row.get('metrics')}")
        print()
        print("Ожидание: [revenue, ordered_units, hits_view]")
        print("Если порядок совпадает — гипотеза подтверждена")
    else:
        print(r.text[:300])


if __name__ == "__main__":
    main()