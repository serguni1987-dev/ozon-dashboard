src = open("run.py", encoding="utf-8").read()

# Ищем блок с sync_finance и добавляем после него fetch-скрипты
old = '''    # 3. Финансы из API
    print("\\n[3] Синхронизация финансов из Ozon API...")
    run([PY, "sync_finance.py"], stop_on_error=False)'''

new = '''    # 3. Финансы из API
    print("\\n[3] Синхронизация финансов из Ozon API...")
    run([PY, "sync_finance.py"], stop_on_error=False)

    # 4. Актуальные цены из Ozon API
    print("\\n[4] Актуальные цены из Ozon API...")
    run([PY, "fetch_current_prices.py"], stop_on_error=False)

    # 5. Актуальные остатки из Ozon API
    print("\\n[5] Актуальные остатки из Ozon API...")
    run([PY, "fetch_current_stocks.py"], stop_on_error=False)'''

if old in src:
    src = src.replace(old, new)
    print("[OK] Добавлены fetch_current_prices + fetch_current_stocks")
else:
    print("[?] Не нашёл блок sync_finance")

open("run.py", "w", encoding="utf-8").write(src)
print("\\nГотово. Запускай: py run.py")
