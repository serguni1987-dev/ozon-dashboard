"""Найти в API признаки возвратов.

Смотрим accrued_category в каждом accrual за месяц.
"""
import sys
from collections import Counter
from datetime import date, timedelta

from .. import config
from ..ozon_client import OzonClient


def main():
    if len(sys.argv) < 2:
        print("Укажи месяц: py -m unitka._diag.find_returns 2026-08")
        return
    month = sys.argv[1]  # 'YYYY-MM'
    y, m = map(int, month.split("-"))
    d = date(y, m, 1)
    end = date(y + (1 if m == 12 else 0), 1 if m == 12 else m + 1, 1)

    config.check_credentials()
    client = OzonClient(config.OZON_CLIENT_ID, config.OZON_API_KEY,
                        base=config.OZON_BASE_URL)

    cats = Counter()
    total = 0
    examples = {}

    cur = d
    while cur < end:
        day = cur.strftime("%Y-%m-%d")
        try:
            accruals = client.accrual_by_day_all(day)
        except Exception as e:
            print(f"  {day}: ERROR {e}")
            cur += timedelta(days=1)
            continue

        for acc in accruals:
            total += 1
            cat = acc.get("accrued_category") or "?"
            cats[cat] += 1
            if cat not in examples:
                examples[cat] = day
        cur += timedelta(days=1)

    print(f"Всего accruals за {month}: {total}")
    print()
    print("accrued_category:")
    for cat, n in cats.most_common():
        print(f"  {cat:<25}  n={n:>5}  пример: {examples[cat]}")


if __name__ == "__main__":
    main()
