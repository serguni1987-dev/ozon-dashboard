src = open("sync_pnl.py", encoding="utf-8").read()

REPL = [
    ('("    - обратная логистика", None)', '("    - обратная логистика", "fulfil_reverse")'),
    ('("    - последняя миля", None)',     '("    - последняя миля", "fulfil_lastmile")'),
    ('("    - обработка, сборка", None)',  '("    - обработка, сборка", "fulfil_processing")'),
    ('("    - отзывы", None)',             '("    - отзывы", "reviews")'),
]

for old, new in REPL:
    if old in src:
        src = src.replace(old, new, 1)
        print(f"[OK] {old[:40]}... → {new[-30:]}")
    else:
        print(f"[?] Не нашёл: {old}")

open("sync_pnl.py", "w", encoding="utf-8").write(src)
print("[OK] sync_pnl.py сохранён")