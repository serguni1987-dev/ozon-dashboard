from datetime import datetime, timedelta
from unitka import config
from unitka.ozon_client import OzonClient
import inspect

# Смотрим, какие аргументы принимает OzonClient
print("=== Аргументы OzonClient.__init__ ===")
print(inspect.signature(OzonClient.__init__))

# Правильный вызов
config.check_credentials()
client = OzonClient()

test_date = "2026-10-15"  # берём день, где по базе пусто
print(f"\n=== Тест API за {test_date} ===")

try:
    acc = client.accrual_by_day(test_date)
    print(f"Начисления: получено {len(acc.get('accruals', []))} записей")
except Exception as e:
    print(f"Начисления: ОШИБКА - {e}")

try:
    payload = {
        "dir": "ASC",
        "filter": {"since": f"{test_date}T00:00:00Z", "to": f"{test_date}T23:59:59Z"},
        "limit": 10,
        "offset": 0
    }
    post = client._post("/v3/posting/fbs/list", payload)
    n = len(post.get('result', {}).get('postings', []))
    print(f"Отправления FBS: получено {n} записей")
except Exception as e:
    print(f"Отправления FBS: ОШИБКА - {e}")