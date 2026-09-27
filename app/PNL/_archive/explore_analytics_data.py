"""
explore_analytics_data.py
Разведка того, какие метрики/измерения поддерживает /v1/analytics/data.
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

# Метрики, которые по документации Ozon потенциально доступны.
# Проверим, какие реально принимает наш аккаунт.
METRICS_TO_TEST = [
    "revenue",                       # выручка
    "ordered_units",                 # заказано штук
    "hits_view_search",              # показы в поиске
    "hits_view_pdp",                 # показы на карточке
    "hits_view",                     # всего показов
    "hits_tocart_search",            # в корзину из поиска
    "hits_tocart_pdp",               # в корзину с карточки
    "hits_tocart",                   # всего в корзину
    "session_view_search",           # сессии из поиска
    "session_view_pdp",              # сессии карточки
    "session_view",                  # всего сессий
    "conv_tocart_search",            # конверсия в корзину из поиска
    "conv_tocart_pdp",               # конверсия в корзину с карточки
    "conv_tocart",                   # конверсия в корзину общая
    "conv_view",                     # конверсия в просмотр
    "conv_pdp_to_cart",              # конверсия карточка→корзина
    "returns",                       # возвраты
    "cancellations",                 # отмены
    "delivered_units",               # доставлено штук
]


def try_metrics(metrics, dimension, extra_filter=None):
    """Пробует запрос с указанными метриками и измерением."""
    payload = {
        "date_from": "2026-08-01",
        "date_to": "2026-08-31",
        "metrics": metrics,
        "dimension": dimension,
        "filters": extra_filter or [],
        "limit": 5,
        "offset": 0,
    }
    r = requests.post(BASE_URL + "/v1/analytics/data", headers=HEADERS, json=payload, timeout=20)
    return r.status_code, r.text


def main():
    # Разбиваем метрики на чанки по 14
    chunks = [METRICS_TO_TEST[i:i+14] for i in range(0, len(METRICS_TO_TEST), 14)]
    all_ok_metrics = []
    all_failed_metrics = []

    for idx, chunk in enumerate(chunks, 1):
        print(f"=== Чанк {idx}/{len(chunks)}: {len(chunk)} метрик, dimension=[day] ===")
        status, text = try_metrics(chunk, ["day"])
        print(f"Статус: {status}")
        if status != 200:
            print(f"Ответ: {text[:500]}")
            all_failed_metrics.extend(chunk)
            print()
            continue
        data = json.loads(text)
        rows = data.get("result", {}).get("data", [])
        print(f"Вернулось строк: {len(rows)}")
        if rows:
            print("Пример строки:")
            print(json.dumps(rows[0], ensure_ascii=False, indent=2))
            # Смотрим, какие ключи реально есть в ответе
            print("Доступные поля в ответе:", list(rows[0].keys()))
        all_ok_metrics.extend(chunk)
        print()

    print(f"\nИтого метрик принято: {len(all_ok_metrics)}")
    print(f"Отклонено: {len(all_failed_metrics)}")
    if all_failed_metrics:
        print("Отклонённые:", all_failed_metrics)

    # Если всё ок — проверим day+sku на первом чанке
    print("\n=== Проверка dimension=[day, sku] ===")
    first_chunk = chunks[0]
    status, text = try_metrics(first_chunk, ["day", "sku"])
    print(f"Статус: {status}")
    if status == 200:
        data = json.loads(text)
        rows = data.get("result", {}).get("data", [])
        print(f"Строк: {len(rows)}")
        if rows:
            print("Пример строки:")
            print(json.dumps(rows[0], ensure_ascii=False, indent=2))
    else:
        print(f"Ответ: {text[:500]}")
if __name__ == "__main__":
    main()