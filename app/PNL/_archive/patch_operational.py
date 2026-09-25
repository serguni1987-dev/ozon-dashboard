import re
src = open("sync_pnl.py", encoding="utf-8").read()

# 1) Функция add_calc_formulas
if "def add_calc_formulas" in src:
    print("[i] add_calc_formulas уже есть")
else:
    FUNC = '''
def add_calc_formulas(rows):
    """Динамические строки P&L:
    - строки 34-37: год B = SUM(C:N), кварталы O:R = SUM(3 месяца)
    - строка 33 (Операционные всего) = SUM(34:37)
    - строка 39 EBITDA = Валовая(31) − Операционные(33)
    - строка 43 Чистая = EBITDA(39) − Налоги(41)
    - строка 44 ROI    = -Чистая(43) / Себестоимость(29) * 100
    """
    COL_YEAR = 2
    COL_MONTH_1 = 3
    COL_Q1 = 15

    def year_sum(row_idx):
        c1 = col_letter(COL_MONTH_1)
        c12 = col_letter(COL_MONTH_1 + 11)
        r = row_idx + 1
        rows[row_idx][COL_YEAR - 1] = f"=SUM({c1}{r}:{c12}{r})"

    def quarter_sums(row_idx):
        r = row_idx + 1
        for q in range(1, 5):
            m1 = (q - 1) * 3 + 1
            m2 = m1 + 2
            cA = col_letter(COL_MONTH_1 + m1 - 1)
            cB = col_letter(COL_MONTH_1 + m2 - 1)
            rows[row_idx][COL_Q1 + q - 1 - 1] = f"=SUM({cA}{r}:{cB}{r})"

    # Строки 34-37: год и кварталы = суммы месяцев
    for ri in (33, 34, 35, 36):
        year_sum(ri)
        quarter_sums(ri)

    # Строка 33: Операционные всего = SUM(34:37)
    for m in range(1, 13):
        c = col_letter(COL_MONTH_1 + m - 1)
        idx = COL_MONTH_1 + m - 1 - 1
        rows[32][idx] = f"=SUM({c}34:{c}37)"
    year_sum(32)
    quarter_sums(32)

    # Строка 39: EBITDA = 31 − 33
    for idx in range(1, 18):
        col = col_letter(idx + 1)
        rows[38][idx] = f"={col}31-{col}33"

    # Строка 43: Чистая = 39 − 41
    for idx in range(1, 18):
        col = col_letter(idx + 1)
        rows[42][idx] = f"={col}39-{col}41"

    # Строка 44: ROI = -43 / 29 * 100 (защита от деления на 0)
    for idx in range(1, 18):
        col = col_letter(idx + 1)
        rows[43][idx] = f"=IF({col}29=0,0,-{col}43/{col}29*100)"


'''
    marker = "def build_table(year=2026):"
    if marker not in src:
        raise SystemExit("Не нашёл def build_table")
    src = src.replace(marker, FUNC + marker, 1)
    print("[OK] add_calc_formulas добавлена")

# 2) Вызов add_calc_formulas(rows) перед return rows внутри build_table
bt = src.find("def build_table(year=2026):")
af = src.find("def apply_format", bt)
if bt < 0 or af < 0:
    raise SystemExit("Не нашёл границы build_table / apply_format")

body = src[bt:af]
if "add_calc_formulas(rows)" not in body:
    # заменить последний "return rows" в этом фрагменте
    idx = body.rfind("return rows")
    if idx < 0:
        raise SystemExit("Не нашёл return rows внутри build_table")
    body = body[:idx] + "add_calc_formulas(rows)\n    " + body[idx:]
    src = src[:bt] + body + src[af:]
    print("[OK] Вызов add_calc_formulas вставлен")
else:
    print("[i] Вызов уже есть")

open("sync_pnl.py", "w", encoding="utf-8").write(src)
print("[OK] sync_pnl.py сохранён")
