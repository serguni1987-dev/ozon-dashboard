src = open("sync_pnl.py", encoding="utf-8").read()

# 1. Чистая = B39 + B41 (в 41 уже минус)
old1 = 'rows[42][idx] = f"={col}39-{col}41"'
new1 = 'rows[42][idx] = f"={col}39+{col}41"'
if old1 in src:
    src = src.replace(old1, new1)
    print("[OK] Чистая: - → +")
else:
    print("[?] Не нашёл формулу чистой")

# 2. ROI — заменить запятые на ;
old2 = 'rows[43][idx] = f"=IF({col}29=0,0,-{col}43/{col}29*100)"'
new2 = 'rows[43][idx] = f"=IF({col}29=0;0;-{col}43/{col}29*100)"'
if old2 in src:
    src = src.replace(old2, new2)
    print("[OK] ROI: запятые → ;")
else:
    print("[?] Не нашёл формулу ROI")

# 3. Заодно — колонка B и кварталы для 33, 39, 43, 44
# Строка 33 = SUM(B34:B37) — уже верно
# Строка 39 = B31-B33 — верно
# Строка 43 = B39+B41 — заменить
old3 = 'rows[38][idx] = f"={col}31-{col}33"'
if old3 in src:
    print("[i] Строка 39 уже верна (B31-B33)")

open("sync_pnl.py", "w", encoding="utf-8").write(src)
print("[OK] sync_pnl.py сохранён")