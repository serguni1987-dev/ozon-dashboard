"""
find_realization_posting.py — ищем рабочие параметры для отчёта о реализации.
"""
import os
import json
import requests
from datetime import datetime
from dotenv import load_dotenv

APP_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(APP_DIR, ".env"))

H = {
    "Client-Id": os.getenv("OZON_CLIENT_ID"),
    "Api-Key": os.getenv("OZON_API_KEY"),
    "Content-Type": "application/json",
}

# Сначала посмотрим, какие методы вообще есть
print("=" * 80)
print("ПОИСК РАБОЧЕГО МЕТОДА ДЛЯ ОТЧЁТА О РЕАЛИЗАЦИИ")
print("=" * 80)

# Список эндпоинтов, которые стоит проверить
endpoints = [
    ("/v1/finance/realization/posting", {"month": 8, "year": 2026}),
    ("/v1/finance/realization/posting", {"month": 8, "year": 2026, "page": 1, "page_size": 1000}),
    ("/v1/finance/realization/posting/list", {"month": 8, "year": 2026}),
    ("/v2/finance/realization/posting", {"month": 8, "year": 2026}),
    ("/v1/finance/posting/list", {"month": 8, "year": 2026}),
    ("/v1/finance/realization", {"month": 8, "year": 2026}),
    ("/v2/finance/realization", {"month": 8, "year": 2026}),
    ("/v3/finance/realization", {"month": 8, "year": 2026}),
    ("/v1/finance/realization/by-day", {"date": "2026-08-15"}),
    ("/v1/finance/realization/rows", {"month": 8, "year": 2026, "page": 1, "page_size": 100}),
]

base = "https://api-seller.ozon.ru"

for path, body in endpoints:
    print(f"\n{'=' * 70}")
    print(f"POST {path}")
    print(f"Body: {json.dumps(body, ensure_ascii=False)}")
    try:
        r = requests.post(base + path, headers=H, json=body, timeout=60)
        print(f"HTTP: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            # Ищем список
            result = data.get("result") or {}
            if isinstance(result, dict):
                rows = result.get("rows") or result.get("items") or []
                header = result.get("header") or {}
            else:
                rows = result if isinstance(result, list) else []
                header = {}
            print(f"  Строк: {len(rows)}")
            if header:
                print(f"  Header: {json.dumps(header, ensure_ascii=False)[:150]}")
            if rows:
                print(f"  🎯 ЕСТЬ ДАННЫЕ! Первая строка:")
                print(f"  {json.dumps(rows[0], ensure_ascii=False)[:600]}")
                print(f"\n  ✅ РАБОЧИЙ МЕТОД: {path}")
                break
        else:
            err = r.text[:200]
            print(f"  Ошибка: {err}")
    except Exception as e:
        print(f"  Исключение: {e}")

print("\n" + "=" * 80)
