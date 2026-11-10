from unitka.ozon_client import OzonClient

client = OzonClient()
print("Клиент создан, ключи подхватились из config")

test_date = "2026-10-15"
print(f"Проверяем /v4/posting/fbs/list за {test_date}...")

payload = {
    "dir": "ASC",
    "filter": {"since": f"{test_date}T00:00:00Z", "to": f"{test_date}T23:59:59Z"},
    "limit": 10,
    "offset": 0
}

try:
    data = client._post("/v4/posting/fbs/list", payload)
    postings = data.get("result", {}).get("postings") or data.get("postings") or []
    print(f"УСПЕХ. Получено {len(postings)} отправлений.")
    if postings:
        print(f"Пример posting_number: {postings[0].get('posting_number')}")
except Exception as e:
    print(f"ОШИБКА: {e}")