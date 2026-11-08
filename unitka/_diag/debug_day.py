from unitka import config
from unitka.ozon_client import OzonClient
import json
config.check_credentials()
c = OzonClient(config.OZON_CLIENT_ID, config.OZON_API_KEY, base=config.OZON_BASE_URL)

data = c.accrual_by_day_all("2026-09-15")
print(f"Всего accruals: {len(data)}")
for acc in data:
    posting = acc.get("posting") or {}
    if posting.get("posting_number", "").startswith("50313579-0458"):
        print("\n=== НАЙДЕНО ===")
        print(f"  accrual_id: {acc.get('accrual_id')}")
        print(f"  unit_number: {acc.get('unit_number')}")
        print(f"  posting.posting_number: {posting.get('posting_number')}")
        print(f"  posting keys: {list(posting.keys())}")
        print(f"  posting.order_id: {posting.get('order_id')}")
        for prod in (posting.get("products") or []):
            if prod.get("sku") == 1605108599:
                print(f"  products.sku: {prod.get('sku')}")
                print(f"  products.commission: {json.dumps(prod.get('commission'), ensure_ascii=False)[:400]}")
                break
        break
else:
    print("\nНЕ найдено. Смотрим первый accrual для примера:")
    for acc in data[:3]:
        posting = acc.get("posting") or {}
        print(f"  unit={acc.get('unit_number')} posting={posting.get('posting_number')} "
              f"skus={[p.get('sku') for p in posting.get('products') or []]}")