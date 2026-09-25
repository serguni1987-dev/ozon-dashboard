"""Патч: ItemCompensation (25) + перенос 59/71 из обратной логистики.
Правит PNL/sync_pnl.py.
"""
import re

src = open("PNL/sync_pnl.py", encoding="utf-8").read()
changed = []

# ── 1. CATEGORY_MAP: 59 → Логистика, 71 → Услуги FBO, +25 ItemCompensation ──
repl = [
    ('59: "Обратная логистика", 71: "Обратная логистика", 45: "Обратная логистика"',
     '59: "Логистика", 71: "Услуги FBO", 45: "Обратная логистика"'),
    ('29: "Последняя миля", 98: "Последняя миля"',
     '29: "Последняя миля", 98: "Последняя миля",\n    25: "ItemCompensation"'),
]
for old, new in repl:
    if old in src:
        src = src.replace(old, new, 1)
        changed.append(f"[OK] CATEGORY_MAP: {old[:40]}...")
    else:
        changed.append(f"[?] не нашёл: {old[:60]}")

# ── 2. expenses_no_ads: вычесть ItemCompensation ──
old_expr = 'services_no_ads = sum(v for k, v in cats.items() if k != "Реклама")'
new_expr = ('services_no_ads = sum(v for k, v in cats.items()\n'
            '                       if k not in ("Реклама", "ItemCompensation"))')
if old_expr in src:
    src = src.replace(old_expr, new_expr, 1)
    changed.append("[OK] services_no_ads: ItemCompensation исключён из суммы")
else:
    changed.append("[?] не нашёл services_no_ads")

old_exp = 'expenses_no_ads = commission + services_no_ads'
new_exp = ('expenses_no_ads = commission + services_no_ads '
           '- cats.get("ItemCompensation", 0)')
if old_exp in src:
    src = src.replace(old_exp, new_exp, 1)
    changed.append("[OK] expenses_no_ads: вычитаем ItemCompensation")
else:
    changed.append("[?] не нашёл expenses_no_ads")

open("PNL/sync_pnl.py", "w", encoding="utf-8").write(src)
for c in changed:
    print(c)
print("[OK] PNL/sync_pnl.py сохранён")