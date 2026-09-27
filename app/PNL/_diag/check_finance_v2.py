"""
check_finance_v2.py
Проверка 3 критичных методов для юнит-экономики.
"""
import os, json, time, requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
CID, KEY = os.getenv("OZON_CLIENT_ID"), os.getenv("OZON_API_KEY")
BASE = os.getenv("OZON_BASE_URL", "https://api-seller.ozon.ru")
H = {"Client-Id": CID, "Api-Key": KEY, "Content-Type": "application/json"}
PAUSE = 5

def call(method, path, payload=None):
    try:
        if method == "GET":
            r = requests.get(BASE + path, headers=H, timeout=30)
        else:
            r = requests.post(BASE + path, headers=H, json=payload or {}, timeout=30)
        return r.status_code, r.text
    except Exception as e:
        return None, str(e)

def show(title, path, status, text):
    print(f"\n{'='*70}")
    print(f"{title} — {path}")
    print(f"{'='*70}")
    print(f"Статус: {status}")
    if status == 200:
        try:
            data = json.loads(text)
            print(f"Ключи: {list(data.keys())}")
            print(json.dumps(data, ensure_ascii=False, indent=2)[:2000])
        except Exception as e:
            print(f"Parse error: {e}")
            print(text[:500])
    else:
        print(text[:400])

def main():
    # Получим первые 3 SKU из БД
    import sqlite3
    conn = sqlite3.connect("ozon.db")
    cur = conn.execute("""
        SELECT sku FROM sales_daily
        WHERE sku IN (SELECT sku FROM products WHERE is_own=1)
        GROUP BY sku ORDER BY SUM(revenue) DESC LIMIT 3
    """)
    skus = [str(r[0]) for r in cur.fetchall()]
    conn.close()
    print(f"Тестовые SKU: {skus}\n")

    # 1. /v5/product/info/prices — комиссии по SKU
    st, tx = call("POST", "/v5/product/info/prices", {
        "filter": {"sku": skus, "visibility": "ALL"},
        "limit": 3,
    })
    show("1. Комиссии по SKU", "/v5/product/info/prices", st, tx)
    time.sleep(PAUSE)

    # 2. /v1/finance/accrual/types — справочник типов начислений
    st, tx = call("POST", "/v1/finance/accrual/types", {})
    show("2. Справочник начислений", "/v1/finance/accrual/types", st, tx)
    time.sleep(PAUSE)

    # 3. /v1/analytics/stocks — аналитика остатков
    st, tx = call("POST", "/v1/analytics/stocks", {"skus": skus})
    show("3. Аналитика остатков", "/v1/analytics/stocks", st, tx)

if __name__ == "__main__":
    main()