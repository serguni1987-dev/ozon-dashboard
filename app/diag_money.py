src = open("sheets_sync.py", encoding="utf-8").read()

# Проверим текущее состояние build_money
idx = src.find("def build_money")
print("=== build_money сейчас ===")
print(src[idx:idx+2000])
