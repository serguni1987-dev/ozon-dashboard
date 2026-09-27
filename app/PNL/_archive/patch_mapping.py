"""Патч sync_pnl.py: правильный CATEGORY_MAP + фикс ABS."""
import os, shutil
from datetime import datetime

SRC = "PNL/sync_pnl.py"
bak = f"{SRC}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
shutil.copy(SRC, bak)
print(f"Бэкап: {bak}")

src = open(SRC, encoding="utf-8").read()

# ── 1. Правки CATEGORY_MAP ───────────────────────────────
changes = [
    ('    18: "Услуги агентов",\n',
     '    18: "Другие услуги",   # EarlyPayment -> Ozon: Другие услуги\n'),
    ('    20: "Услуги агентов",\n',
     '    20: "Другие услуги",   # FlexiblePayments -> Ozon: Другие услуги\n'),
    ('    22: "Услуги агентов",\n',
     '    22: "Реклама PPC",      # Installment -> Ozon: Продвижение и реклама\n'),
    ('    74: "Звёзды",              # StarsMembership\n',
     '    74: "Услуги агентов",   # StarsMembership -> Ozon: Услуги партнёров\n'),
    ('    52: "Другие услуги",\n',
     '    52: "Реклама PPC",      # PremiumSubscription -> Ozon: Продвижение и реклама\n'),
    ('    78: "Обработка, сборка", 79: "Обработка, сборка",\n',
     '    78: "Другие услуги",   # TemporaryPlacement -> Ozon: Другие услуги\n    79: "Услуги агентов",   # TemporaryPlacementsAgent -> Ozon: Услуги партнёров\n'),
]

for old, new in changes:
    if old in src:
        src = src.replace(old, new)
        print(f"[OK] {old.strip()[:50]}  ->  {new.strip()[:50]}")
    else:
        print(f"[?] НЕ найден: {old.strip()[:60]}")

# ── 2. Фикс ABS: не берём abs при накоплении ─────────────
old_abs = 'cats[cat] = cats.get(cat, 0) + abs(f(row["total"]))'
new_abs = 'cats[cat] = cats.get(cat, 0) + f(row["total"])'

if old_abs in src:
    src = src.replace(old_abs, new_abs)
    print(f"[OK] abs() убран из накопления cats")
else:
    print(f"[?] НЕ найден фрагмент abs()")

# ── 3. При выводе округлений категорий — взять abs ──────
# В строке ads = cats.get("Реклама PPC", 0) — тоже abs для вывода
# Уже сделано через f() — оставим как есть

open(SRC, "w", encoding="utf-8").write(src)
print()
print("[OK] Файл обновлён")
