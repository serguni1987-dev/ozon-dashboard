src = open("fetch_current_stocks.py", encoding="utf-8").read()

# 1. Отправляем cursor вместо last_id
old_body = '''    body = {
        "filter": {"visibility": "ALL"},
        "last_id": last_id,
        "limit": 1000,
    }'''
new_body = '''    body = {
        "filter": {"visibility": "ALL"},
        "cursor": last_id,
        "limit": 1000,
    }'''
if old_body in src:
    src = src.replace(old_body, new_body)
    print("[OK] body: last_id → cursor")
else:
    print("[?] Не нашёл body")

# 2. Читаем cursor из ответа
old_read = '''    items = data.get("items") or []
    last_id_new = data.get("last_id") or ""
    return items, last_id_new'''
new_read = '''    items = data.get("items") or []
    last_id_new = data.get("cursor") or ""
    return items, last_id_new'''
if old_read in src:
    src = src.replace(old_read, new_read)
    print("[OK] читаем cursor из ответа")
else:
    print("[?] Не нашёл чтение last_id")

open("fetch_current_stocks.py", "w", encoding="utf-8").write(src)
print("\nГотово. Запускай: py fetch_current_stocks.py")
