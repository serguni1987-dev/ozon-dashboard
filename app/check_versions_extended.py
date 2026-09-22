"""
check_versions_extended.py
Расширенная проверка эндпоинтов Seller API + пробный Performance API.
Ключи из .env.
"""
import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("OZON_CLIENT_ID")
API_KEY = os.getenv("OZON_API_KEY")
BASE_URL = os.getenv("OZON_BASE_URL", "https://api-seller.ozon.ru")

if not CLIENT_ID or not API_KEY:
    raise SystemExit("[ERROR] OZON_CLIENT_ID / OZON_API_KEY не найдены в .env")

HEADERS = {
    "Client-Id": CLIENT_ID,
    "Api-Key": API_KEY,
    "Content-Type": "application/json",
}

# Пример рабочих product_ids получим динамически из /v3/product/list
def get_sample_product_ids():
    r = requests.post(BASE_URL + "/v3/product/list", headers=HEADERS,
                      json={"filter": {"offer_id": []}, "last_id": "", "limit": 5})
    if r.status_code != 200:
        return []
    items = r.json().get("result", {}).get("items", [])
    return [it["product_id"] for it in items]


def get_sample_skus():
    r = requests.post(BASE_URL + "/v3/product/list", headers=HEADERS,
                      json={"filter": {"offer_id": []}, "last_id": "", "limit": 5})
    if r.status_code != 200:
        return []
    items = r.json().get("result", {}).get("items", [])
    return [it["sku"] for it in items]


# Тестовые сценарии
def build_test_cases():
    sample_ids = get_sample_product_ids()
    sample_skus = get_sample_skus()
    print(f"Тестовые product_ids: {sample_ids}")
    print(f"Тестовые skus: {sample_skus}\n")

    return [
        # --- Аналитика (правильный payload) ---
        ("POST", "/v1/analytics/data", {
            "date_from": "2026-08-01",
            "date_to": "2026-09-01",
            "metrics": ["ordered_units", "revenue"],
            "dimension": ["day", "sku"],
            "filters": [],
            "limit": 5,
            "offset": 0
        }),
        # --- Баланс / финансы ---
        ("POST", "/v1/finance/balance", {
            "date_from": "2026-08-01", "date_to": "2026-09-01"
        }),
        # --- Отзывы ---
        ("POST", "/v2/review/list", {"limit": 5, "last_id": "", "sort_dir": "ASC"}),
        # --- Акции Ozon ---
        ("GET",  "/v1/actions", None),
        # --- Акции продавца ---
        ("POST", "/v1/seller-actions/list", {"limit": 5, "offset": 0}),
        # --- Склады ---
        ("POST", "/v2/warehouse/list", {"limit": 5, "cursor": ""}),
        # --- Premium: поисковые запросы ---
        ("POST", "/v1/analytics/product-queries", {
            "date_from": "2026-08-01", "date_to": "2026-09-01",
            "skus": sample_skus, "page": 0, "page_size": 5,
            "sort_by": "BY_SEARCHES", "sort_dir": "DESCENDING"
        }),
        # --- Premium: аналитика остатков ---
        ("POST", "/v1/analytics/stocks", {"skus": sample_skus}),
        # --- Premium: детали цен ---
        ("POST", "/v1/product/prices/details", {"skus": sample_skus}),
    ]


def check_all():
    test_cases = build_test_cases()
    print(f"Проверяем {len(test_cases)} эндпоинтов\n")
    results = []
    for method, path, payload in test_cases:
        url = BASE_URL + path
        try:
            t0 = time.time()
            if method == "GET":
                r = requests.get(url, headers=HEADERS, timeout=15)
            else:
                r = requests.post(url, headers=HEADERS, json=payload, timeout=15)
            dt = round((time.time() - t0) * 1000)
            status = r.status_code
            ok = status == 200
            results.append((path, status, ok))
            marker = "OK  " if ok else "FAIL"
            print(f"[{marker}] {status:>3} {dt:>5}ms  {path}")
            if not ok:
                text = r.text[:200].replace("\n", " ")
                print(f"        {text}")
        except Exception as e:
            results.append((path, None, False))
            print(f"[ERR ] ---      {path}")
            print(f"        {type(e).__name__}: {e}")
        time.sleep(0.2)

    ok_count = sum(1 for _, _, ok in results if ok)
    print(f"\nИтого: {ok_count}/{len(test_cases)} работают")


if __name__ == "__main__":
    check_all()