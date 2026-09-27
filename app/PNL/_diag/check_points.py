# check_points.py
# Разведка /v1/finance/accrual/by-day — сколько комиссии начислено
# и сколько компенсировано баллами. Считаем эффективную комиссию.

import os
import json
import requests
from collections import defaultdict
from datetime import datetime, timedelta
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

DATE_FROM = "2026-09-01T00:00:00Z"
DATE_TO   = "2026-09-30T23:59:59Z"


def post(path, body):
    url = BASE_URL.rstrip("/") + path
    r = requests.post(url, headers=HEADERS, json=body, timeout=60)
    if r.status_code != 200:
        print(f"[{r.status_code}] {path}")
        print(r.text[:2000])
        r.raise_for_status()
    return r.json()


def get_types():
    """Справочник типов начислений: id -> name."""
    data = post("/v1/finance/accrual/types", {})
    types = {}
    for t in data.get("accrual_types", []) or data.get("result", []):
        types[t.get("id") or t.get("code")] = t.get("name") or t.get("title")
    return types


def get_by_day(date_from, date_to):
    """Начисления по дням. Пагинация на всякий случай."""
    all_rows = []
    page = 1
    while True:
        body = {
            "date": {"from": date_from, "to": date_to},
            "page": page,
            "page_size": 1000,
        }
        data = post("/v1/finance/accrual/by-day", body)
        rows = data.get("accruals") or data.get("result") or data.get("data") or []
        if not rows:
            if page == 1:
                print("СЫРОЙ ОТВЕТ (первые 3000 символов):")
                print(json.dumps(data, ensure_ascii=False, indent=2)[:3000])
            break
        all_rows.extend(rows)
        if len(rows) < 1000:
            break
        page += 1
    return all_rows


def main():
    print("=" * 100)
    print("РАЗВЕДКА /v1/finance/accrual/by-day — комиссия vs баллы")
    print("=" * 100)

    print("\n[1] Справочник типов начислений...")
    try:
        types = get_types()
        for k, v in types.items():
            print(f"  {k}: {v}")
    except Exception as e:
        print(f"  Не удалось получить справочник: {e}")
        types = {}

    print(f"\n[2] Начисления с {DATE_FROM} по {DATE_TO}...")
    rows = get_by_day(DATE_FROM, DATE_TO)
    print(f"  Получено строк: {len(rows)}")

    if not rows:
        print("\nПусто. Смотрим сырой ответ выше.")
        return

    print("\n[3] Структура первой строки:")
    print(json.dumps(rows[0], ensure_ascii=False, indent=2))

    # Попытка агрегировать по типу
    by_type = defaultdict(float)
    by_date = defaultdict(lambda: defaultdict(float))

    for row in rows:
        # Ищем поле с суммой и типом — названия могут отличаться
        amount = (
            row.get("amount")
            or row.get("sum")
            or row.get("accrual_amount")
            or 0
        )
        type_id = (
            row.get("accrual_type_id")
            or row.get("type_id")
            or row.get("accrual_type")
            or row.get("type")
        )
        date = row.get("date") or row.get("accrual_date") or row.get("day")

        name = types.get(type_id, str(type_id))
        by_type[name] += float(amount)
        if date:
            by_date[date][name] += float(amount)

    print("\n[4] ИТОГО по типам начислений:")
    print("-" * 80)
    for name, total in sorted(by_type.items(), key=lambda x: -abs(x[1])):
        print(f"  {name:<60} {total:>15,.2f} ₽")

    print("\n[5] По дням (только комиссия и компенсации):")
    print("-" * 80)
    key_commission = [k for k in by_type if "комис" in k.lower() or "commission" in k.lower()]
    key_points     = [k for k in by_type if "балл" in k.lower() or "point" in k.lower() or "компенс" in k.lower()]

    print(f"  Ключи комиссии: {key_commission}")
    print(f"  Ключи баллов:   {key_points}")
    print()

    for d in sorted(by_date.keys()):
        day = by_date[d]
        comm = sum(day.get(k, 0) for k in key_commission)
        pts  = sum(day.get(k, 0) for k in key_points)
        print(f"  {d}   комиссия: {comm:>12,.2f}   баллы: {pts:>12,.2f}   эффективно: {comm + pts:>12,.2f}")

    total_comm = sum(by_type.get(k, 0) for k in key_commission)
    total_pts  = sum(by_type.get(k, 0) for k in key_points)
    print("\n" + "=" * 100)
    print(f"  Всего комиссии:              {total_comm:>15,.2f} ₽")
    print(f"  Всего баллов (компенсаций):  {total_pts:>15,.2f} ₽")
    print(f"  Эффективно списано:          {total_comm + total_pts:>15,.2f} ₽")
    if total_comm:
        print(f"  Доля компенсации:            {-total_pts / total_comm * 100:>14.1f} %")
    print("=" * 100)


if __name__ == "__main__":
    main()