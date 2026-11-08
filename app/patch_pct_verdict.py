"""patch_pct_verdict: C = % от базы, T = выводы. Сдвигает месяцы C-N -> D-O, кварталы O-R -> P-S."""
import shutil, re
from datetime import datetime

# ─── 1. sync_pnl.py ───
SRC = "PNL/sync_pnl.py"
bak = f"{SRC}.bak-pct-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
shutil.copy(SRC, bak)
print(f"Бэкап 1: {bak}")

src = open(SRC, encoding="utf-8").read()

# 1.1 Добавить make_verdict после QUARTERS
anchor = '''QUARTERS = ["1 кв", "2 кв", "3 кв", "4 кв"]'''
verdict_fn = anchor + '''


def make_verdict(label, pct_signed):
    """Текстовый вердикт для колонки T."""
    lbl = label.strip().lower()
    # маржинальные — знаковые
    if "валовая прибыль" in lbl or "чистая прибыль" in lbl or "ebitda" in lbl:
        if pct_signed >= 20: return "✓ норма"
        if pct_signed >= 10: return "⚠ средне"
        if pct_signed >= 0:  return "⚠ низко"
        return "!! убыток"
    if "доходы" in lbl:
        return "✓ база"
    # расходные — по модулю
    pct = abs(pct_signed)
    if "комиссия" in lbl:
        if pct <= 45: return "✓ норма"
        if pct <= 55: return "⚠ высоко"
        return "!! критично"
    if "логистика" in lbl and "обратная" not in lbl:
        if pct <= 8: return "✓ норма"
        if pct <= 12: return "⚠ высоко"
        return "!! критично"
    if "себестоимость" in lbl:
        if pct <= 35: return "✓ норма"
        if pct <= 45: return "⚠ высоко"
        return "!! критично"
    if "реклама" in lbl:
        if pct <= 10: return "✓ норма"
        if pct <= 15: return "⚠ высоко"
        return "!! критично"
    return ""'''

if anchor in src and "def make_verdict" not in src:
    src = src.replace(anchor, verdict_fn, 1)
    print("[OK] make_verdict добавлена")
else:
    print("[?] anchor для make_verdict или уже есть")

# 1.2 Константы — теперь сдвиг + COL_PCT + COL_VERDICT
old_consts = '''    COL_YEAR = 2
    COL_MONTH_1 = 3
    COL_Q1 = 15'''
new_consts = '''    COL_YEAR = 2
    COL_PCT = 3
    COL_MONTH_1 = 4
    COL_Q1 = 16
    COL_VERDICT = 20'''
count = src.count(old_consts)
src = src.replace(old_consts, new_consts)
print(f"[OK] константы обновлены ({count} мест)")

# 1.3 Заголовок — длина 20
src = src.replace(
    'rows.append(["Отчёт о прибылях и убытках OZON"] + [""] * 18)',
    'rows.append(["Отчёт о прибылях и убытках OZON"] + [""] * 19)')
print("[OK] длина заголовка → 20")

# 1.4 row2 — добавить C и T
old_row2 = '''    row2 = [""] * 19
    row2[1] = f"Всего за {year}"
    for i, name in enumerate(MONTHS):
        row2[mcol(i + 1) - 1] = name
    for i, name in enumerate(QUARTERS):
        row2[qcol(i + 1) - 1] = name
    rows.append(row2)'''
new_row2 = '''    row2 = [""] * 20
    row2[1] = f"Всего за {year}"
    row2[2] = "%"
    for i, name in enumerate(MONTHS):
        row2[mcol(i + 1) - 1] = name
    for i, name in enumerate(QUARTERS):
        row2[qcol(i + 1) - 1] = name
    row2[19] = "выводы"
    rows.append(row2)'''
if old_row2 in src:
    src = src.replace(old_row2, new_row2)
    print("[OK] row2 обновлён")
else:
    print("[?] row2 не найден")

# 1.5 Основной цикл — row = 20, добавить C и T
old_loop = '''    for label, key in lines:
        row = [""] * 19
        row[0] = label
        if key is None:
            rows.append(row)
            continue

        r_num = len(rows) + 1
        c1 = col_letter(COL_MONTH_1)
        c12 = col_letter(COL_MONTH_1 + 11)
        row[COL_YEAR - 1] = f"=SUM({c1}{r_num}:{c12}{r_num})"

        for m_str, data in by_month.items():
            m_num = int(m_str.split("-")[1])
            val = data.get(key, 0)
            if key in NEGATIVE:
                val = -abs(val)
            row[mcol(m_num) - 1] = round(val, 2)

        for q in range(1, 5):
            m1 = (q - 1) * 3 + 1
            m2 = m1 + 2
            cA = col_letter(mcol(m1))
            cB = col_letter(mcol(m2))
            row[qcol(q) - 1] = f"=SUM({cA}{r_num}:{cB}{r_num})"

        rows.append(row)'''

new_loop = '''    base_year = sum(d.get("revenue", 0) for d in by_month.values())

    for label, key in lines:
        row = [""] * 20
        row[0] = label
        if key is None:
            rows.append(row)
            continue

        r_num = len(rows) + 1
        c1 = col_letter(COL_MONTH_1)
        c12 = col_letter(COL_MONTH_1 + 11)
        row[COL_YEAR - 1] = f"=SUM({c1}{r_num}:{c12}{r_num})"
        row[COL_PCT - 1] = f"=IF($B$5=0;0;B{r_num}/$B$5*100)"

        for m_str, data in by_month.items():
            m_num = int(m_str.split("-")[1])
            val = data.get(key, 0)
            if key in NEGATIVE:
                val = -abs(val)
            row[mcol(m_num) - 1] = round(val, 2)

        for q in range(1, 5):
            m1 = (q - 1) * 3 + 1
            m2 = m1 + 2
            cA = col_letter(mcol(m1))
            cB = col_letter(mcol(m2))
            row[qcol(q) - 1] = f"=SUM({cA}{r_num}:{cB}{r_num})"

        year_val = sum(d.get(key, 0) for d in by_month.values())
        if key in NEGATIVE:
            year_val = -abs(year_val)
        pct_signed = (year_val / base_year * 100) if base_year else 0
        row[COL_VERDICT - 1] = make_verdict(label, pct_signed)

        rows.append(row)'''

if old_loop in src:
    src = src.replace(old_loop, new_loop)
    print("[OK] основной цикл обновлён")
else:
    print("[?] основной цикл не найден")

# 1.6 add_calc_formulas — диапазоны до T (не включая)
src = src.replace("for idx in range(1, 18):", "for idx in range(1, 19):")
print("[OK] диапазоны в add_calc_formulas расширены")

# 1.7 read_operational — сдвиг C..N -> D..O
old_ro = '''            # C..N = 1-based колонки 3..14 = 0-based индексы 2..13
            for idx in range(2, 14):'''
new_ro = '''            # D..O = 1-based колонки 4..15 = 0-based индексы 3..14
            for idx in range(3, 15):'''
if old_ro in src:
    src = src.replace(old_ro, new_ro)
    print("[OK] read_operational → D..O")
else:
    print("[?] read_operational не найден")

# 1.8 apply_format — расширить S -> T
for old, new in [('"A1:S1"', '"A1:T1"'), ('"A2:S2"', '"A2:T2"'),
                 ('"B3:S{n_rows}"', '"B3:T{n_rows}"'),
                 ('"B44:S44"', '"B44:T44"')]:
    src = src.replace(old, new)
src = re.sub(r'f"A\{r\}:S\{r\}"', 'f"A{r}:T{r}"', src)
src = re.sub(r'f"A\{r\}"', 'f"A{r}"', src)  # без изменений, оставим
print("[OK] apply_format расширен до T")

open(SRC, "w", encoding="utf-8").write(src)
print()

# ─── 2. fix_sheet_full.py ───
SRC2 = "PNL/fix_sheet_full.py"
bak2 = f"{SRC2}.bak-pct-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
shutil.copy(SRC2, bak2)
print(f"Бэкап 2: {bak2}")

src2 = open(SRC2, encoding="utf-8").read()

# MONTHS — сдвиг C..N -> D..O
src2 = src2.replace('MONTHS=[cl(i) for i in range(3,15)]',
                    'MONTHS=[cl(i) for i in range(4,16)]  # D..O')
src2 = src2.replace('MONTHS=[cl(i) for i in range(3, 15)]',
                    'MONTHS=[cl(i) for i in range(4, 16)]  # D..O')
# QUARTERS — сдвиг
src2 = src2.replace(
    'QUARTERS={"O":("C","E"),"P":("F","H"),"Q":("I","K"),"R":("L","N")}',
    'QUARTERS={"P":("D","F"),"Q":("G","I"),"R":("J","L"),"S":("M","O")}')

# B-формулы для C (столбец %) не должны затирать формулу из sync_pnl.
# В SUM_ROWS формула B-колонки ставится как =SUM(C..N). Заменяем на C..N → D..O
src2 = src2.replace('f"=SUM(C{r}:N{r})"', 'f"=SUM(D{r}:O{r})"')
src2 = src2.replace('"=SUM(B37:B40)"', '"=SUM(B37:B40)"')  # не трогаем

open(SRC2, "w", encoding="utf-8").write(src2)
print("[OK] fix_sheet_full.py обновлён")
print()

# ─── 3. pnl_format.py — расширить до 20 колонок ───
SRC3 = "PNL/pnl_format.py"
bak3 = f"{SRC3}.bak-pct-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
shutil.copy(SRC3, bak3)
print(f"Бэкап 3: {bak3}")

src3 = open(SRC3, encoding="utf-8").read()
src3 = src3.replace('def grid(sid,r0,r1,c0=0,c1=19):', 'def grid(sid,r0,r1,c0=0,c1=20):')
src3 = src3.replace('grid(sid,2,N,1,19)', 'grid(sid,2,N,1,20)')
src3 = src3.replace('grid(sid,46,47,1,19)', 'grid(sid,46,47,1,20)')
open(SRC3, "w", encoding="utf-8").write(src3)
print("[OK] pnl_format.py расширен до T")
print()
print("Готово. Пересинкай:")
print("  py PNL\\sync_pnl.py 2026 --local")
print("  py PNL\\sync_pnl.py 2026")
print("  py PNL\\pnl_format.py")
print("  py PNL\\fix_sheet_full.py")
