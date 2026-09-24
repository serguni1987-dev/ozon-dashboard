import re
src = open("sync_pnl.py", encoding="utf-8").read()

# ── 1. CATEGORY_MAP ─────────────────────────────────
NEW_MAP = '''CATEGORY_MAP = {
    # фулфилмент
    32: "Логистика",  77: "Логистика",
    59: "Обратная логистика", 71: "Обратная логистика", 45: "Обратная логистика",
    29: "Последняя миля", 98: "Последняя миля",
    12: "Обработка, сборка", 16: "Обработка, сборка", 38: "Обработка, сборка",
    39: "Обработка, сборка", 78: "Обработка, сборка", 79: "Обработка, сборка",
    # маркетинг — РАСШИРЕНО
    41: "Реклама PPC",        # PayPerClick
    54: "Продвижение",         # Promotion
    74: "Звёзды",              # StarsMembership
    3:  "Бренд-комиссия",      # BrandCommission
    47: "Отзывы",              # PointsForReviews
    96: "Отзывы",              # AcceleratedReviewCollection
    # агенты
    1:  "Услуги агентов", 18: "Услуги агентов",
    20: "Услуги агентов", 22: "Услуги агентов",
    # FBO
    46: "Услуги FBO", 76: "Услуги FBO",
    # другие
    14: "Другие услуги", 15: "Другие услуги", 48: "Другие услуги",
    52: "Другие услуги", 93: "Другие услуги", 94: "Другие услуги",
    # прочие
    6: "Прочие", 9: "Прочие", 40: "Прочие",
}
'''
m = re.search(r'CATEGORY_MAP\s*=\s*\{[^}]+\}', src, re.DOTALL)
if m:
    src = src[:m.start()] + NEW_MAP + src[m.end():]
    print("[OK] CATEGORY_MAP заменён")

# ── 2. return в get_pnl_for_month ────────────────────
NEW_RETURN = '''return {
        "orders": orders, "bonus": bonus, "revenue": revenue,
        "sale_price": sale_price, "coinv": coinv, "commission": commission,
        "cogs": cogs,
        "fulfil_logistics":  cats.get("Логистика", 0),
        "fulfil_reverse":    cats.get("Обратная логистика", 0),
        "fulfil_lastmile":   cats.get("Последняя миля", 0),
        "fulfil_processing": cats.get("Обработка, сборка", 0),
        "fulfil_total":     (cats.get("Логистика", 0) + cats.get("Обратная логистика", 0)
                              + cats.get("Последняя миля", 0) + cats.get("Обработка, сборка", 0)),
        "ppc":   cats.get("Реклама PPC", 0),
        "promo": cats.get("Продвижение", 0),
        "stars": cats.get("Звёзды", 0),
        "brand": cats.get("Бренд-комиссия", 0),
        "reviews": cats.get("Отзывы", 0),
        "market_total": (cats.get("Реклама PPC", 0) + cats.get("Продвижение", 0)
                         + cats.get("Звёзды", 0) + cats.get("Бренд-комиссия", 0)
                         + cats.get("Отзывы", 0)),
        "agents": cats.get("Услуги агентов", 0),
        "fbo": cats.get("Услуги FBO", 0),
        "other": cats.get("Другие услуги", 0),
        "misc": cats.get("Прочие", 0), "ads": ads,
        "expenses_no_ads": expenses_no_ads,
        "expenses_total": expenses_no_ads + ads,
        "margin": margin, "tax_base": tax_base, "tax": tax, "net": net, "roi": roi,
    }
'''
m = re.search(r'return\s*\{[^}]+\}', src, re.DOTALL)
if m:
    src = src[:m.start()] + NEW_RETURN + src[m.end():]
    print("[OK] return заменён")

# ── 3. lines ─────────────────────────────────────────
NEW_LINES = '''lines = [
        ("Заказы (справочно)", "orders"),
        ("Начислено баллов", "bonus"),
        ("Всего к начислению (Отчёт о реализации)", "revenue"),
        ("Сумма Отчёта о реализации", "sale_price"),
        ("", None),
        ("ДОХОДЫ", "revenue"),
        ("  Выручка за вычетом возвратов", "sale_price"),
        ("  Баллы за скидки", "bonus"),
        ("  Программы партнёров", "coinv"),
        ("  Компенсации", None),
        ("", None),
        ("Прямые (переменные) расходы (всего)", "expenses_total"),
        ("  Озон комиссия (за вычетом возвратов)", "commission"),
        ("  Озон фулфилмент:", "fulfil_total"),
        ("    - логистика", "fulfil_logistics"),
        ("    - обратная логистика", "fulfil_reverse"),
        ("    - последняя миля", "fulfil_lastmile"),
        ("    - обработка, сборка", "fulfil_processing"),
        ("  Озон маркетинг:", "market_total"),
        ("    - реклама (PayPerClick)", "ppc"),
        ("    - продвижение, промо", "promo"),
        ("    - звёзды (Stars)", "stars"),
        ("    - бренд-комиссия", "brand"),
        ("    - отзывы", "reviews"),
        ("  Услуги агентов (эквайринг и пр.)", "agents"),
        ("  Услуги FBO", "fbo"),
        ("  Другие услуги", "other"),
        ("  Прочие начисления", "misc"),
        ("", None),
        ("  Себестоимость с учётом возвратов", "cogs"),
        ("", None),
        ("ВАЛОВАЯ ПРИБЫЛЬ", "margin"),
        ("", None),
        ("Операционные расходы (всего)", None),
        ("  - расходы на персонал", None),
        ("  - административные расходы", None),
        ("  - коммерческие расходы", None),
        ("  - прочие операционные расходы", None),
        ("", None),
        ("ОПЕРАЦИОННАЯ ПРИБЫЛЬ (EBITDA)", "margin"),
        ("", None),
        ("Налоги (УСН 15%)", "tax"),
        ("", None),
        ("ЧИСТАЯ ПРИБЫЛЬ", "net"),
        ("Рентабельность (ROI)", "roi"),
        ("Выплата дивидендов", None),
        ("Нераспределённая прибыль", "net"),
        ("Накопленная прибыль", "net"),
    ]
'''
m = re.search(r'lines\s*=\s*\[.*?\]', src, re.DOTALL)
if m:
    src = src[:m.start()] + NEW_LINES + src[m.end():]
    print("[OK] lines заменён")

# ── 4. NEGATIVE ──────────────────────────────────────
NEW_NEG = '''NEGATIVE = {"expenses_total", "expenses_no_ads", "cogs", "commission",
                "fulfil_total", "fulfil_logistics", "fulfil_reverse",
                "fulfil_lastmile", "fulfil_processing", "reviews",
                "ppc", "promo", "stars", "brand", "market_total",
                "agents", "fbo", "other", "misc", "tax"}'''
m = re.search(r'NEGATIVE\s*=\s*\{[^}]+\}', src, re.DOTALL)
if m:
    src = src[:m.start()] + NEW_NEG + src[m.end():]
    print("[OK] NEGATIVE заменён")

# ── 5. read_operational — строки 34-37 → 37-40 ──────
src = src.replace('for r in (34, 35, 36, 37):', 'for r in (37, 38, 39, 40):')
print("[OK] read_operational: 37-40")

# ── 6. add_calc_formulas — переписать целиком ────────
NEW_CALC = '''def add_calc_formulas(rows):
    """Строки:
       36 = SUM(37:40)  Операционные всего
       37-40           Операционные подстроки (ручной ввод C:N)
       42 = 34 - 36    EBITDA
       46 = 42 + 44    Чистая (44 — налог, уже со знаком минус)
       47 = -46/32*100 ROI
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

    for ri in (36, 37, 38, 39):
        year_sum(ri); quarter_sums(ri)

    for m in range(1, 13):
        c = col_letter(COL_MONTH_1 + m - 1)
        idx = COL_MONTH_1 + m - 1 - 1
        rows[35][idx] = f"=SUM({c}37:{c}40)"
    year_sum(35); quarter_sums(35)

    for idx in range(1, 18):
        col = col_letter(idx + 1)
        rows[41][idx] = f"={col}34-{col}36"
    for idx in range(1, 18):
        col = col_letter(idx + 1)
        rows[45][idx] = f"={col}42+{col}44"
    for idx in range(1, 18):
        col = col_letter(idx + 1)
        rows[46][idx] = f"=IF({col}32=0;0;-{col}46/{col}32*100)"


'''
m = re.search(r'def add_calc_formulas\(rows\):.*?(?=def build_table)', src, re.DOTALL)
if m:
    src = src[:m.start()] + NEW_CALC + src[m.end():]
    print("[OK] add_calc_formulas переписан")

open("sync_pnl.py", "w", encoding="utf-8").write(src)
print("[OK] sync_pnl.py сохранён")