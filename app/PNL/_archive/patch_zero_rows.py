import re
src = open("sync_pnl.py", encoding="utf-8").read()

# ── 1. В get_pnl_for_month добавить поля с дефолтом 0 ──
# Ищем return в конце get_pnl_for_month
if '"fulfil_reverse"' not in src:
    # Добавляем 4 ключа перед закрывающей скобкой return
    old_return = '"margin": margin, "tax_base": tax_base, "tax": tax, "net": net, "roi": roi,'
    new_return = (old_return + '\n        "fulfil_reverse":    cats.get("Обратная логистика", 0),'
                              + '\n        "fulfil_lastmile":   cats.get("Последняя миля", 0),'
                              + '\n        "fulfil_processing": cats.get("Обработка, сборка", 0),'
                              + '\n        "reviews":           cats.get("Отзывы", 0),')
    if old_return in src:
        src = src.replace(old_return, new_return, 1)
        print("[OK] 4 новых ключа добавлены в get_pnl_for_month")
    else:
        print("[?] Не нашёл return в get_pnl_for_month — ищи вручную строку с margin/tax/net/roi")
else:
    print("[i] Ключи уже есть")

# ── 2. Заменить None на реальные ключи в списке lines ──
repl = [
    ('("    - обратная логистика", None)', '("    - обратная логистика", "fulfil_reverse")'),
    ('("    - последняя миля", None)',     '("    - последняя миля", "fulfil_lastmile")'),
    ('("    - обработка, сборка", None)',  '("    - обработка, сборка", "fulfil_processing")'),
    ('("    - отзывы", None)',             '("    - отзывы", "reviews")'),
]
for old, new in repl:
    if old in src:
        src = src.replace(old, new, 1)
        print(f"[OK] {old[:35]}... → {new[-20:]}")
    else:
        print(f"[?] Не нашёл: {old}")

# ── 3. Добавить ключи в NEGATIVE ──
old_neg = 'NEGATIVE = {"expenses_total", "expenses_no_ads", "cogs", "commission", "logistics",'
if old_neg in src:
    new_neg = old_neg.replace('"logistics",',
        '"logistics", "fulfil_reverse", "fulfil_lastmile", "fulfil_processing", "reviews",')
    src = src.replace(old_neg, new_neg, 1)
    print("[OK] 4 ключа добавлены в NEGATIVE")
else:
    # если строка по-другому оформлена — предупредим
    if '"fulfil_reverse"' in src and 'NEGATIVE' in src:
        # проверим что там уже есть
        m = re.search(r'NEGATIVE\s*=\s*\{[^}]+\}', src)
        if m and 'fulfil_reverse' not in m.group(0):
            print("[!] NEGATIVE найден, но не по шаблону. Пришли строку:")
            print("  ", m.group(0)[:200])
        else:
            print("[i] NEGATIVE уже содержит новые ключи")
    else:
        print("[?] Не нашёл NEGATIVE")

open("sync_pnl.py", "w", encoding="utf-8").write(src)
print("[OK] sync_pnl.py сохранён")