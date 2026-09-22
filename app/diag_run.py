src = open("run.py", encoding="utf-8").read()

# Смотрим, что реально в run.py
print("=== run.py ===")
for line in src.splitlines():
    if "print(" in line and ("[" in line):
        print(f"  {line.strip()}")
print()

# Добавляем fetch-скрипты, если их нет
if "fetch_current_prices" not in src:
    # Ищем точку после sync_finance
    old_marker = 'run([PY, "sync_finance.py"], stop_on_error=False)'
    if old_marker in src:
        new_block = old_marker + '''

    # Актуальные цены из Ozon API
    print("\\n[4] Актуальные цены из Ozon API...")
    run([PY, "fetch_current_prices.py"], stop_on_error=False)

    # Актуальные остатки из Ozon API
    print("\\n[5] Актуальные остатки из Ozon API...")
    run([PY, "fetch_current_stocks.py"], stop_on_error=False)'''
        src = src.replace(old_marker, new_block, 1)
        print("[OK] fetch-скрипты добавлены в run.py")
    else:
        print("[FAIL] Не нашёл вызов sync_finance")
else:
    print("[i] fetch_current_prices уже есть")
