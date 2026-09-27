"""patch5: правильная замена 48 с учётом inline-формата + 77 в fbo."""
import shutil, re
from datetime import datetime

# ── 1. sync_pnl.py ──
SRC1 = "PNL/sync_pnl.py"
bak1 = f"{SRC1}.bak5-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
shutil.copy(SRC1, bak1)
print(f"Бэкап 1: {bak1}")

src = open(SRC1, encoding="utf-8").read()

# Найти строку, где есть 48: "Другие услуги", разобрать её, пересобрать
pattern = re.compile(r'^( *)20: "Другие услуги", 48: "Другие услуги", 78: "Другие услуги",', re.MULTILINE)
m = pattern.search(src)
if m:
    indent = m.group(1)
    new_line = (
        f'{indent}20: "Другие услуги", 78: "Другие услуги",\n'
        f'{indent}48: "Реклама PPC",      # PremiumCashback -> Ozon: Продвижение и реклама'
    )
    src = pattern.sub(new_line, src, count=1)
    print(f"[OK] 48 вынесен в отдельную строку как Реклама PPC")
    open(SRC1, "w", encoding="utf-8").write(src)
else:
    print("[?] не нашёл строку с 20/48/78")
    for line in src.splitlines():
        if "48:" in line:
            print(f"    найдено: {line!r}")

# ── 2. compare_ozon.py: 77 в fbo ──
SRC2 = "PNL/_diag/compare_ozon.py"
bak2 = f"{SRC2}.bak5-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
shutil.copy(SRC2, bak2)
print(f"Бэкап 2: {bak2}")

src2 = open(SRC2, encoding="utf-8").read()
old_fbo = '"fbo":      [46, 71, 76, 12],'
new_fbo = '"fbo":      [46, 71, 76, 12, 77],'
if old_fbo in src2:
    src2 = src2.replace(old_fbo, new_fbo)
    print("[OK] 77 добавлен в fbo")
else:
    print(f"[?] не найден блок fbo")
    for line in src2.splitlines():
        if '"fbo"' in line:
            print(f"    найдено: {line!r}")

open(SRC2, "w", encoding="utf-8").write(src2)
print()
