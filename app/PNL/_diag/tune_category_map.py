"""tune_category_map.py — диагностика маппинга type_id по всем 8 месяцам."""
import sqlite3, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import sync_pnl

# Эталон Ozon из «Отчёта по экономике» (скрины личного кабинета)
OZON = {
    "2026-01": {"commission": 168655.42, "fulfil": 44984.26, "agents":  7544.85,
                "fbo": 5490.75, "other": 31719.82, "marketing": 69855.99, "compens": 0},
    "2026-02": {"commission": 103478.18, "fulfil": 21950.05, "agents":  5182.71,
                "fbo": 1764.60, "other":  2198.51, "marketing": 45999.74, "compens": 0},
    "2026-03": {"commission":  47112.73, "fulfil":  7594.85, "agents":  1707.94,
                "fbo": 4630.90, "other":  1911.55, "marketing": 48411.25, "compens": 0},
    "2026-04": {"commission":  38450.85, "fulfil":  6602.92, "agents":  1575.66,
                "fbo": 4781.75, "other":   707.76, "marketing":  6847.79, "compens": 0},
    "2026-05": {"commission":  28996.68, "fulfil":  4046.00, "agents":  1876.48,
                "fbo": 9388.75, "other":  1338.96, "marketing": 18081.96, "compens": 0},
    "2026-06": {"commission":   7345.61, "fulfil":  3490.00, "agents":   632.50,
                "fbo": 4493.70, "other":     0.00, "marketing":     0.00, "compens": 6177.00},
    "2026-07": {"commission":   3646.73, "fulfil":   300.00, "agents":   356.45,
                "fbo":    0.00, "other":    33.00, "marketing":     0.00, "compens": 0},
    "2026-08": {"commission": 151050.09, "fulfil":  9850.00, "agents":  9028.00,
                "fbo":  721.00, "other":  5078.00, "marketing":   292.00, "compens": 0},
}

# Группы CATEGORY_MAP, соответствующие строкам эталона
GROUPS = {
    "commission":  None,  # берём из monthly_realization_rows
    "fulfil":     ["Логистика", "Обратная логистика", "Последняя миля", "Обработка, сборка"],
    "agents":     ["Услуги агентов"],
    "fbo":        ["Услуги FBO"],
    "other":      ["Другие услуги"],
    "marketing":  ["Реклама PPC", "Продвижение", "Звёзды", "Бренд-комиссия", "Отзывы"],
}

con = sqlite3.connect(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "ozon.db"))
con.row_factory = sqlite3.Row

def month_bounds(month):
    y, m = month.split("-")
    ny, nm = (int(y) + 1, 1) if m == "12" else (int(y), int(m) + 1)
    return f"{month}-01", f"{ny}-{nm:02d}-01"

def commission(month):
    r = con.execute("""
        SELECT SUM(gross_commission) FROM monthly_realization_rows WHERE month = ?
    """, (month,)).fetchone()
    return abs(r[0] or 0)

print("=" * 100)
print("СРАВНЕНИЕ ПО КАТЕГОРИЯМ: эталон Ozon vs наш CATEGORY_MAP")
print("=" * 100)

# --- Сводка по месяцам ---
header = f"{'Мес':<8} | {'Категория':<12} | {'Ozon':>12} | {'Наше':>12} | {'Δ':>12} | {'Δ%':>7}"
print(header)
print("-" * 100)

problems = []  # (month, cat, diff)

for month in OZON:
    d1, d2 = month_bounds(month)
    # Суммы по категориям CATEGORY_MAP
    cats = {}
    for row in con.execute("""
        SELECT type_id, SUM(ABS(amount)) AS total
        FROM accruals_services WHERE date >= ? AND date < ?
        GROUP BY type_id
    """, (d1, d2)):
        cat = sync_pnl.CATEGORY_MAP.get(row["type_id"], "Без категории")
        cats[cat] = cats.get(cat, 0) + (row["total"] or 0)

    our = {}
    our["commission"] = commission(month)
    for key, cat_list in GROUPS.items():
        if cat_list is None: continue
        our[key] = sum(cats.get(c, 0) for c in cat_list)

    for key in ("commission", "fulfil", "agents", "fbo", "other", "marketing"):
        oz = OZON[month][key]
        ou = our.get(key, 0)
        d = ou - oz
        pct = (d / oz * 100) if oz else 0
        flag = "!!" if abs(d) > 500 else "  "
        print(f"{month:<8} | {key:<12} | {oz:>12,.0f} | {ou:>12,.0f} | {d:>+12,.0f} | {pct:>+6.1f}% {flag}")
        if abs(d) > 500:
            problems.append((month, key, d))
    print("-" * 100)

print()
print(f"Проблемных пар (месяц, категория): {len(problems)}")
for m, c, d in problems:
    print(f"  {m}  {c:<12}  Δ = {d:>+12,.0f}")

# --- По каждому type_id: в какую категорию попадает, суммы по месяцам ---
print()
print("=" * 100)
print("СПОРНЫЕ type_id (встречаются только в проблемных месяцах)")
print("=" * 100)

# Собираем type_id, которые есть в проблемных месяцах, но отсутствуют в чистых (апр, май)
problem_months = sorted(set(m for m, _, _ in problems))
clean_months   = ["2026-04", "2026-05"]

def ids_in(months):
    ids = set()
    for m in months:
        d1, d2 = month_bounds(m)
        for r in con.execute("""
            SELECT DISTINCT type_id FROM accruals_services
            WHERE date >= ? AND date < ?
        """, (d1, d2)):
            ids.add(r["type_id"])
    return ids

prob_ids  = ids_in(problem_months)
clean_ids = ids_in(clean_months)
suspects  = sorted(prob_ids - clean_ids)

print(f"type_id, которых нет в апреле/мае: {len(suspects)}")
print()
print(f"{'id':>4} | {'name':<32} | {'мес':>5} | {'сумма':>12} | текущая категория")
print("-" * 100)

rows_out = []
for tid in suspects:
    cat = sync_pnl.CATEGORY_MAP.get(tid, "!!! БЕЗ КАТЕГОРИИ !!!")
    total = 0
    n_months = 0
    for m in problem_months:
        d1, d2 = month_bounds(m)
        r = con.execute("""
            SELECT type_name, SUM(ABS(amount)) AS total, COUNT(*) AS n
            FROM accruals_services
            WHERE type_id = ? AND date >= ? AND date < ?
        """, (tid, d1, d2)).fetchone()
        if r and r["total"]:
            total += r["total"]
            n_months += 1
            name = r["type_name"] or "?"
    if total > 0:
        rows_out.append((tid, name, n_months, total, cat))

rows_out.sort(key=lambda x: -x[3])
for tid, name, nm, total, cat in rows_out:
    print(f"{tid:>4} | {name[:32]:<32} | {nm:>5} | {total:>12,.2f} | {cat}")

con.close()
