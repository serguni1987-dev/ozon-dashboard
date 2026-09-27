"""patch4: 48 PremiumCashback -> Реклама PPC."""
import shutil
from datetime import datetime

# ── 1. sync_pnl.py ──
SRC1 = "PNL/sync_pnl.py"
bak1 = f"{SRC1}.bak4-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
shutil.copy(SRC1, bak1)
print(f"Бэкап 1: {bak1}")

src = open(SRC1, encoding="utf-8").read()
old = '    48: "Другие услуги",'
new = '    48: "Реклама PPC",      # PremiumCashback -> Ozon: Реклама'
if old in src:
    src = src.replace(old, new)
    print("[OK] 48 -> Реклама PPC")
else:
    print("[?] не найден 48 в CATEGORY_MAP")
open(SRC1, "w", encoding="utf-8").write(src)

# ── 2. compare_ozon.py ──
SRC2 = "PNL/_diag/compare_ozon.py"
bak2 = f"{SRC2}.bak4-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
shutil.copy(SRC2, bak2)
print(f"Бэкап 2: {bak2}")

src2 = open(SRC2, encoding="utf-8").read()
old_g = '"other":    [14, 15, 18, 20, 48, 78, 93, 94],'
new_g = '"other":    [14, 15, 18, 20, 78, 93, 94],'
if old_g in src2:
    src2 = src2.replace(old_g, new_g)
    print("[OK] GROUPS: 48 убран из other")

old_d = '"dRR":      [41, 54, 3, 47, 96, 22, 52],'
new_d = '"dRR":      [41, 54, 3, 47, 96, 22, 52, 48],'
if old_d in src2:
    src2 = src2.replace(old_d, new_d)
    print("[OK] GROUPS: 48 добавлен в dRR")

open(SRC2, "w", encoding="utf-8").write(src2)
print()
