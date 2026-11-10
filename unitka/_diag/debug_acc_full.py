from unitka import config
from unitka.ozon_client import OzonClient
import json
config.check_credentials()
c = OzonClient()

data = c.accrual_by_day_all("2026-09-15")
print(f"Всего accruals: {len(data)}")

# ищем тот, у которого sku=1605108599 (seller_price=11802)
for i, acc in enumerate(data):
    posting = acc.get("posting") or {}
    skus = [p.get("sku") for p in (posting.get("products") or [])]
    if 1605108599 in skus:
        print(f"\n=== НАЙДЕНО, индекс {i} ===")
        print(f"accrual_id: {acc.get('accrual_id')}")
        print(f"unit_number: {acc.get('unit_number')!r}")
        print(f"posting keys: {list(posting.keys())}")
        print(f"posting.posting_number: {posting.get('posting_number')!r}")
        print(f"posting.order_id: {posting.get('order_id')}")
        print(f"posting.posting_number: {posting.get('posting_number')!r}")
        print(f"all top-level keys: {list(acc.keys())}")
        # сохраним полностью
        with open("acc_sample.json", "w", encoding="utf-8") as f:
            json.dump(acc, f, ensure_ascii=False, indent=2, default=str)
        print("\nсохранено в acc_sample.json (первые 3000 символов):")
        print(json.dumps(acc, ensure_ascii=False, default=str)[:3000])
        break
else:
    print("Не нашли sku=1605108599 за 15.09")
    # для примера выведем первый
    a = data[0]
    print(f"\nПример первого accrual:")
    print(f"  unit_number: {a.get('unit_number')!r}")
    print(f"  keys: {list(a.keys())}")
    p = a.get("posting") or {}
    print(f"  posting keys: {list(p.keys())}")
    print(f"  posting.posting_number: {p.get('posting_number')!r}")