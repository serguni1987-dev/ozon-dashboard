src = open("sync_pnl.py", encoding="utf-8").read()

# Ищем вычисление expenses
old = '''    expenses = expenses_no_ads + ads'''

new = '''    # "Прямые расходы (всего)" БЕЗ рекламы — как в эталоне
    expenses = expenses_no_ads'''

if old in src:
    src = src.replace(old, new)
    open("sync_pnl.py", "w", encoding="utf-8").write(src)
    print("[OK] 'Прямые расходы (всего)' = без рекламы")
else:
    print("[?] Не нашёл 'expenses = expenses_no_ads + ads'")

# Проверяем, что margin считается с учётом рекламы
old2 = '''    margin = revenue - expenses - cogs'''
new2 = '''    margin = revenue - expenses_no_ads - ads - cogs'''
if old2 in src:
    src = src.replace(old2, new2)
    print("[OK] margin = revenue − расходы(без рекламы) − реклама − cogs")
else:
    print("[?] Не нашёл 'margin = revenue - expenses - cogs'")
