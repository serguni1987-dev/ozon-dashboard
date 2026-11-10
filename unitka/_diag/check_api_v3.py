import inspect
from unitka import config
from unitka.ozon_client import OzonClient

print("=== Сигнатура __init__ ===")
print(inspect.signature(OzonClient.__init__))

print("\n=== Исходный код __init__ ===")
try:
    print(inspect.getsource(OzonClient.__init__))
except Exception as e:
    print(f"Не удалось получить исходник: {e}")

print("\n=== Доступные методы класса ===")
methods = [m for m in dir(OzonClient) if not m.startswith('__')]
for m in methods:
    print(f"  {m}")

print("\n=== Пробуем создать клиент ===")
try:
    client = OzonClient()
    print("Клиент создан успешно")
except Exception as e:
    print(f"Ошибка создания: {e}")
    exit(1)

test_date = "2026-10-15"
print(f"\n=== Тест 1: accrual_by_day({test_date}) ===")
try:
    if hasattr(client, 'accrual_by_day'):
        acc = client.accrual_by_day(test_date)
        print(f"УСПЕХ. Получено {len(acc.get('accruals', []))} записей")
    else:
        print("Метод accrual_by_day отсутствует")
except Exception as e:
    print(f"ОШИБКА: {e}")

print(f"\n=== Тест 2: _post /v3/posting/fbs/list ===")
try:
    if hasattr(client, '_post'):
        payload = {
            "dir": "ASC",
            "filter": {"since": f"{test_date}T00:00:00Z", "to": f"{test_date}T23:59:59Z"},
            "limit": 10,
            "offset": 0
        }
        post = client._post("/v3/posting/fbs/list", payload)
        n = len(post.get('result', {}).get('postings', []))
        print(f"УСПЕХ. Получено {n} записей")
    else:
        print("Метод _post отсутствует")
except Exception as e:
    print(f"ОШИБКА: {e}")