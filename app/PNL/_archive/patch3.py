"""patch3: 29 и 45 -> агенты."""
import os, shutil, re
from datetime import datetime

# ── 1. sync_pnl.py ──
SRC1 = "PNL/sync_pnl.py"
bak1 = f"{SRC1}.bak3-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
shutil.copy(SRC1, bak1)
print(f"Бэкап 1: {bak1}")

src = open(SRC1, encoding="utf-8").read()

# Заменить весь CATEGORY_MAP
m = re.search(r"CATEGORY_MAP = \{.*?\n\}", src, re.DOTALL)
if not m:
    print("НЕ найден CATEGORY_MAP")
    raise SystemExit(1)

new_block = '''CATEGORY_MAP = {
    # фулфилмент (Ozon «Услуги доставки»)
    32: "Логистика", 59: "Логистика", 98: "Логистика",
    16: "Логистика", 17: "Логистика",
    38: "Обработка, сборка", 39: "Обработка, сборка",
    # агенты (Ozon «Услуги партнёров»)
    1:  "Услуги агентов", 74: "Услуги агентов",
    79: "Услуги агентов", 29: "Услуги агентов",
    45: "Услуги агентов",
    # FBO (Ozon «Услуги FBO»)
    46: "Услуги FBO", 71: "Услуги FBO", 76: "Услуги FBO", 12: "Услуги FBO",
    # маркетинг (Ozon «Продвижение и реклама»)
    41: "Реклама PPC", 54: "Продвижение", 3: "Бренд-комиссия",
    47: "Отзывы", 96: "Отзывы",
    22: "Реклама PPC", 52: "Реклама PPC",
    # другие услуги и штрафы
    14: "Другие услуги", 15: "Другие услуги", 18: "Другие услуги",
    20: "Другие услуги", 48: "Другие услуги", 78: "Другие услуги",
    93: "Другие услуги", 94: "Другие услуги",
    # прочие / компенсации
    25: "ItemCompensation",
    6: "Прочие", 9: "Прочие", 40: "Прочие",
}'''

src = src[:m.start()] + new_block + src[m.end():]
open(SRC1, "w", encoding="utf-8").write(src)
print("[OK] CATEGORY_MAP перезаписан")

# ── 2. compare_ozon.py GROUPS ──
SRC2 = "PNL/_diag/compare_ozon.py"
bak2 = f"{SRC2}.bak3-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
shutil.copy(SRC2, bak2)
print(f"Бэкап 2: {bak2}")

src2 = open(SRC2, encoding="utf-8").read()
m2 = re.search(r"GROUPS = \{.*?\n\}", src2, re.DOTALL)
if not m2:
    print("НЕ найден GROUPS")
    raise SystemExit(2)

new_g = '''GROUPS = {
    "logistic": [32, 59, 98, 16, 17, 38, 39],
    "agents":   [1, 74, 79, 29, 45],
    "fbo":      [46, 71, 76, 12],
    "other":    [14, 15, 18, 20, 48, 78, 93, 94],
    "dRR":      [41, 54, 3, 47, 96, 22, 52],
}'''

src2 = src2[:m2.start()] + new_g + src2[m2.end():]
open(SRC2, "w", encoding="utf-8").write(src2)
print("[OK] GROUPS обновлён")
print()
