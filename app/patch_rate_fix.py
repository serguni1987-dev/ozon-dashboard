src = open("apply_prices.py", encoding="utf-8").read()

# Меняем логику: n_changes > 0 → пропускаем (а не предупреждаем)
old = '''        # Проверка лимита
        n_changes = check_rate_limit(con, oid)
        if n_changes >= RATE_LIMIT_PER_HOUR:
            skipped_rate.append((oid, n_changes))
            continue
        if n_changes > 0:
            skipped_rate.append((oid, n_changes, "warning"))'''

new = '''        # Проверка лимита: если уже менялось за последний час — пропускаем
        n_changes = check_rate_limit(con, oid)
        if n_changes > 0:
            skipped_rate.append((oid, n_changes))
            continue'''

if old in src:
    src = src.replace(old, new)
    print("[OK] Логика лимита исправлена: n_changes > 0 → пропуск")
else:
    print("[?] Не нашёл блок проверки лимита")

# Убираем блок "внимание, но применяем" из вывода
old2 = '''    if skipped_rate:
        print(f"\\n[!] Пропущено из-за лимита {RATE_LIMIT_PER_HOUR}/час:")
        for item in skipped_rate:
            if len(item) == 2:
                print(f"    {item[0]}: {item[1]} изменений за час — пропуск")
            else:
                print(f"    {item[0]}: {item[1]} изменений за час — внимание, но применяем")'''

new2 = '''    if skipped_rate:
        print(f"\\n[!] Пропущено из-за лимита (не чаще 1 раза в час на SKU):")
        for item in skipped_rate:
            print(f"    {item[0]}: уже менялось {item[1]} раз(а) за час — пропуск")'''

if old2 in src:
    src = src.replace(old2, new2)
    print("[OK] Вывод про лимит исправлен")

open("apply_prices.py", "w", encoding="utf-8").write(src)
print("\nГотово.")
