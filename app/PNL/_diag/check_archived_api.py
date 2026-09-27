"""
check_archived_api.py — разведка: получаем список товаров с флагом archived.
"""
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

H = {
    "Client-Id": os.getenv("OZON_CLIENT_ID"),
    "Api-Key": os.getenv("OZON_API_KEY"),
    "Content-Type": "application/json",
}
URL = "https://api-seller.ozon.ru"


def post(path, body):
    r = requests.post(URL + path, headers=H, json=body, timeout=60)
    if r.status_code != 200:
        print(f"[{r.status_code}] {path}")
        print(r.text[:1000])
        return None
    return r.json()


def main():
    print("=" * 90)
    print("РАЗВЕДКА /v3/product/list")
    print("=" * 90)

    # Пробуем разные варианты фильтра
    variants = [
        {"filter": {"visibility": "ALL"}, "last_id": "", "limit": 100},
        {"filter": {"visibility": "ARCHIVED"}, "last_id": "", "limit": 100},
        {"filter": {}, "last_id": "", "limit": 100},
    ]

    for i, body in enumerate(variants, 1):
        print(f"\n--- Вариант {i}: {json.dumps(body, ensure_ascii=False)}")
        data = post("/v3/product/list", body)
        if not data:
            continue
        result = data.get("result") or {}
        items = result.get("items") or []
        total = result.get("total", "?")
        print(f"  total: {total}, items в ответе: {len(items)}")
        if items:
            print("  Первый item:")
            print(json.dumps(items[0], ensure_ascii=False, indent=2))
            print("  Последний item:")
            print(json.dumps(items[-1], ensure_ascii=False, indent=2))
            return


if __name__ == "__main__":
    main()
