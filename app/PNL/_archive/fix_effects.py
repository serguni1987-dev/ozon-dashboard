src = open("decision_effects.py", encoding="utf-8").read()

old = """        if not before and not after:
            print("  Нет данных ни до, ни после.\\n")
            continue

        print(f"  {'Метрика':<14} {'До (30д)':>13} {'После':>13} {'Δ':>10}")"""

new = """        if after is None:
            if before:
                print(f"  Данных «после» ещё нет. «До»: {before['orders']} заказов, "
                      f"прибыль {before['profit']:,.0f} ₽/30д.")
            print()
            continue

        if not before and not after:
            print("  Нет данных ни до, ни после.\\n")
            continue

        print(f"  {'Метрика':<14} {'До (30д)':>13} {'После':>13} {'Δ':>10}")"""

if old in src:
    src = src.replace(old, new)
    open("decision_effects.py", "w", encoding="utf-8").write(src)
    print("[OK] decision_effects.py исправлен")
else:
    print("[?] Не нашёл место для патча")
