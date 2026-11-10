from unitka.ozon_client import OzonClient

client = OzonClient()

print("=== Тест 1: широкий диапазон (как в load_postings) ===")
payload = {
    "dir": "ASC",
    "filter": {"since": "2026-10-01T00:00:00.000Z", "to": "2026-11-09T23:59:59.999Z"},
    "limit": 50,
    "offset": 0
}
try:
    data = client._post("/v4/posting/fbs/list", payload)
    print(f"Ответ: {str(data)[:500]}")
    postings = data.get("result", {}).get("postings") or data.get("postings") or []
    print(f"УСПЕХ. Получено {len(postings)} отправлений.")
except Exception as e:
    print(f"ОШИБКА: {e}")

print("\n=== Тест 2: тот же запрос, но за один день 15 октября ===")
payload2 = {
    "dir": "ASC",
    "filter": {"since": "2026-10-15T00:00:00.000Z", "to": "2026-10-15T23:59:59.999Z"},
    "limit": 50,
    "offset": 0
}
try:
    data = client._post("/v4/posting/fbs/list", payload2)
    postings = data.get("result", {}).get("postings") or data.get("postings") or []
    print(f"УСПЕХ. Получено {len(postings)} отправлений.")
except Exception as e:
    print(f"ОШИБКА: {e}")

print("\n=== Тест 3: без dir, только since/to ===")
payload3 = {
    "filter": {"since": "2026-10-01T00:00:00.000Z", "to": "2026-11-09T23:59:59.999Z"},
    "limit": 50,
    "offset": 0
}
try:
    data = client._post("/v4/posting/fbs/list", payload3)
    postings = data.get("result", {}).get("postings") or data.get("postings") or []
    print(f"УСПЕХ. Получено {len(postings)} отправлений.")
    if postings:
        print(f"Первый: {postings[0].get('posting_number')}")
except Exception as e:
    print(f"ОШИБКА: {e}")