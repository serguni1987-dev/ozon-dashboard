src = open("sheets_sync.py", encoding="utf-8").read()

# Ищем определение net_assets
idx = src.find("net_assets")
if idx > 0:
    print("=== net_assets в коде ===")
    print(src[idx-200:idx+400])

# Ищем блок ЧИСТЫЕ АКТИВЫ в build_capital
idx2 = src.find("ЧИСТЫЕ АКТИВЫ")
if idx2 > 0:
    print()
    print("=== Строка ЧИСТЫЕ АКТИВЫ ===")
    print(src[idx2-100:idx2+300])
