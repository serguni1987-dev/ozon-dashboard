src = open("sync_pnl.py", encoding="utf-8").read()
old = '("Прямые (переменные) расходы (всего)", "expenses_no_ads"),'
new = '("Прямые (переменные) расходы (всего)", "expenses_total"),'
if old in src:
    src = src.replace(old, new)
    open("sync_pnl.py", "w", encoding="utf-8").write(src)
    print("[OK] Прямые теперь включают маркетинг")
else:
    print("[?] Не нашёл строку. Все совпадения с 'Прямые':")
    for line in src.splitlines():
        if "Прямые" in line:
            print(repr(line))
