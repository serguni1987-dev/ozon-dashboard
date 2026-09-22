"""
calc_realization.py
Тянет позаказный отчёт о реализации за прошлый месяц,
извлекает баллы за скидки и считает ЭФФЕКТИВНУЮ комиссию.
"""
import os, json, requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
CID, KEY = os.getenv("OZON_CLIENT_ID"), os.getenv("OZON_API_KEY")
BASE = os.getenv("OZON_BASE_URL", "https://api-seller.ozon.ru")
H = {"Client-Id": CID, "Api-Key": KEY, "Content-Type": "application/json"}


def prev_month():
    today = datetime.now()
    first = today.replace(day=1)
    prev = first - timedelta(days=1)
    return prev.year, prev.month


def main():
    year, month = prev_month()
    print(f"Реализация за {month:02d}.{year}\n")

    r = requests.post(BASE + "/v1/finance/realization/posting",
                      headers=H, json={"year": year, "month": month},
                      timeout=60)
    print(f"Статус: {r.status_code}")
    if r.status_code != 200:
        print(r.text[:400])
        return

    data = r.json()
    rows = data.get("rows", [])
    print(f"Строк: {len(rows)}\n")

    if not rows:
        print("Пусто. Возможно, отчёт ещё не сформирован.")
        return

    # Смотрим поля одной строки
    print("=" * 70)
    print("Структура одной строки:")
    print("=" * 70)
    print(json.dumps(rows[0], ensure_ascii=False, indent=2)[:3000])

    # Ищем ключи, в которых упоминается «балл»
    print("\n" + "=" * 70)
    print("Все ключи с «балл» или «point»:")
    print("=" * 70)
    for k in sorted(rows[0].keys()):
        kl = k.lower()
        if "балл" in kl or "point" in kl or "bonus" in kl:
            print(f"  {k}: {rows[0][k]}")

    # Агрегаты
    print("\n" + "=" * 70)
    print("Агрегаты по строкам:")
    print("=" * 70)
    totals = {}
    for row in rows:
        for k, v in row.items():
            if isinstance(v, (int, float)):
                totals[k] = totals.get(k, 0) + v
    for k in sorted(totals.keys()):
        if abs(totals[k]) > 0.01:
            print(f"  {k}: {totals[k]:,.2f}")


if __name__ == "__main__":
    main()