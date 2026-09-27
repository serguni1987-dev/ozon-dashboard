"""
check_accruals.py
Берём реальные постинги за несколько дней и смотрим фактические начисления.
Поможет понять, что такое net_price и как считаются удержания.
"""
import os, json, time, requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
CID, KEY = os.getenv("OZON_CLIENT_ID"), os.getenv("OZON_API_KEY")
BASE = os.getenv("OZON_BASE_URL", "https://api-seller.ozon.ru")
H = {"Client-Id": CID, "Api-Key": KEY, "Content-Type": "application/json"}


def main():
    # Возьмём последние 14 дней, чтобы были доставленные заказы
    today = datetime.now()
    date_from = (today - timedelta(days=14)).strftime("%Y-%m-%dT00:00:00Z")
    date_to = today.strftime("%Y-%m-%dT23:59:59Z")

    print(f"Период: {date_from} — {date_to}\n")

    # 1. Список постингов FBO
    r = requests.post(BASE + "/v3/posting/fbo/list", headers=H, json={
        "filter": {"since": date_from, "to": date_to, "statuses": ["delivered"]},
        "limit": 100, "sort_dir": "DESC", "cursor": "",
        "with": {"analytics_data": False, "financial_data": True, "legal_info": False},
    }, timeout=60)
    print(f"FBO list: {r.status_code}")
    if r.status_code != 200:
        print(r.text[:400]); return
    fbo = r.json().get("postings", [])
    print(f"Доставленных FBO: {len(fbo)}")

    if not fbo:
        print("Нет доставленных — попробуем FBS")
        r = requests.post(BASE + "/v3/posting/fbs/list", headers=H, json={
            "filter": {"since": date_from, "to": date_to,
                       "statuses": ["delivered"]},
            "limit": 100, "sort_dir": "DESC", "cursor": "",
            "with": {"analytics_data": False, "financial_data": True, "legal_info": False},
        }, timeout=60)
        if r.status_code == 200:
            fbo = r.json().get("postings", [])
            print(f"Доставленных FBS: {len(fbo)}")

    if not fbo:
        print("Нет доставленных заказов за период")
        return

    # 2. Показываем полную структуру одного постинга
    first = fbo[0]
    print("\n" + "=" * 70)
    print("Полная структура одного постинга:")
    print("=" * 70)
    print(json.dumps(first, ensure_ascii=False, indent=2)[:4000])

    # 3. Запрашиваем accruals для нескольких постингов
    numbers = [p.get("posting_number") for p in fbo[:10] if p.get("posting_number")]
    print(f"\nЗапрашиваем accruals для {len(numbers)} постингов...")

    time.sleep(2)
    r = requests.post(BASE + "/v1/finance/accrual/postings", headers=H,
                      json={"posting_numbers": numbers}, timeout=60)
    print(f"accrual/postings: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(json.dumps(data, ensure_ascii=False, indent=2)[:5000])
    else:
        print(r.text[:400])


if __name__ == "__main__":
    main()