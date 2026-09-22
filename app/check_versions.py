"""
check_versions.py
Проверка, какие эндпоинты Ozon Seller API живые.
Ключи читаются из .env, хардкода нет.
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


# Тестовые payload'ы. Ключи (endpoint, method, payload).
TEST_CASES = [
    ("POST", "/v3/product/list", {"filter": {"offer_id": []}, "last_id": "", "limit": 5}),
    ("POST", "/v4/product/info/stocks", {"filter": {"visibility": "ALL"}, "limit": 5}),
    ("POST", "/v3/posting/fbo/list", {
        "filter": {"since": "2026-08-01T00:00:00Z", "to": "2026-09-01T23:59:59Z"},
        "limit": 5, "sort_dir": "ASC", "cursor": ""
    }),
    ("POST", "/v3/posting/fbs/list", {
        "filter": {"since": "2026-08-01T00:00:00Z", "to": "2026-09-01T23:59:59Z"},
        "limit": 5, "sort_dir": "ASC", "cursor": ""
    }),
    ("POST", "/v1/analytics/data", {
        "date_from": "2026-08-01T00:00:00Z", "date_to": "2026-09-01T23:59:59Z",
        "metric_type": "hits", "product_ids": []
    }),
    ("POST", "/v3/finance/transaction/list", {
        "filter": {"date": {"from": "2026-08-01T00:00:00Z", "to": "2026-09-01T23:59:59Z"}},
        "page": 1, "page_size": 5
    }),
    ("POST", "/v1/finance/realization/posting", {"year": 2026, "month": 8}),
    ("POST", "/v1/finance/cash-flow-statement", {
        "date_from": "2026-08-01T00:00:00Z", "date_to": "2026-09-01T23:59:59Z"
    }),
    ("POST", "/v1/rating/summary", {}),
    ("POST", "/v1/returns/list", {
        "filter": {"logistic_return_date": {"time_from": "2026-08-01T00:00:00Z", "time_to": "2026-09-01T23:59:59Z"}},
        "limit": 5, "last_id": 0
    }),
]


def check_all():
    print(f"Проверяем {len(TEST_CASES)} эндпоинтов на {BASE_URL}\n")
    results = []
    for method, path, payload in TEST_CASES:
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
            results.append((path, status, ok, dt))
            marker = "OK  " if ok else "FAIL"
            print(f"[{marker}] {status:>3} {dt:>5}ms  {path}")
            if not ok:
                # покажем короткий кусок ответа, чтобы понять причину
                text = r.text[:200].replace("\n", " ")
                print(f"        {text}")
        except Exception as e:
            results.append((path, None, False, 0))
            print(f"[ERR ] ---      {path}")
            print(f"        {type(e).__name__}: {e}")
        time.sleep(0.2)  # чтобы не упереться в rate limit

    ok_count = sum(1 for _, _, ok, _ in results if ok)
    print(f"\nИтого: {ok_count}/{len(TEST_CASES)} работают")


if __name__ == "__main__":
    check_all()