"""Проверяет: сходится ли эталон, если считать amount со знаком, а ABS — к итогу."""
import sqlite3, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import sync_pnl

OZON = {
    "2026-01": {"commission": 168655.42, "fulfil": 44984.26, "agents":  7544.85,
                "fbo": 5490.75, "other": 31719.82, "marketing": 69855.99},
    "2026-02": {"commission": 103478.18, "fulfil": 21950.05, "agents":  5182.71,
                "fbo": 1764.60, "other":  2198.51, "marketing": 45999.74},
    "2026-03": {"commission":  47112.73, "fulfil":  7594.85, "agents":  1707.94,
                "fbo": 4630.90, "other":  1911.55, "marketing": 48411.25},
    "2026-04": {"commission":  38450.85, "fulfil":  6602.92, "agents":  1575.66,
                "fbo": 4781.75, "other":   707.76, "marketing":  6847.79},
    "2026-05": {"commission":  28996.68, "fulfil":  4046.00, "agents":  1876.48,
                "fbo": 9388.75, "other":  1338.96, "marketing": 18081.96},
    "2026-06": {"commission":   7345.61, "fulfil":  3490.00, "agents":   632.50,
                "fbo": 4493.70, "other":     0.00, "marketing":     0.00},
    "2026-07": {"commission":   3646.73, "fulfil":   300.00, "agents":   356.45,
                "fbo":    0.00, "other":    33.00, "marketing":     0.00},
    "2026-08": {"commission": 151050.09, "fulfil":  9850.00, "agents":  9028.00,
                "fbo":  721.00, "other":  5078.00, "marketing":   292.00},
}

GROUPS = {
    "fulfil":    ["Логистика", "Обратная логистика", "Последняя миля", "Обработка, сборка"],
    "agents":    ["Услуги агентов"],
    "fbo":       ["Услуги FBO"],
    "other":     ["Другие услуги"],
    "marketing": ["Реклама PPC", "Продвижение", "Звёзды", "Бренд-комиссия", "Отзывы"],
}

con = sqlite3.connect(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "ozon.db"))
con.row_factory = sqlite3.Row

def month_bounds(month):
    y, m = month.split("-")
    ny, nm = (int(y) + 1, 1) if m == "12" else (int(y), int(m) + 1)
    return f"{month}-01", f"{ny}-{nm:02d}-01"

def compute(month, use_abs_per_row):
    d1, d2 = month_bounds(month)
    cats = {}
    for row in con.execute("""
        SELECT type_id, amount FROM accruals_services
        WHERE date >= ? AND date < ?
    """, (d1, d2)):
        cat = sync_pnl.CATEGORY_MAP.get(row["type_id"], "Без категории")
        v = abs(row["amount"]) if use_abs_per_row else row["amount"]
        cats[cat] = cats.get(cat, 0) + v
    out = {}
    for key, cat_list in GROUPS.items():
        # abs к итогу
        out[key] = abs(sum(cats.get(c, 0) for c in cat_list))
    return out

print(f"{'Мес':<10} | {'Категория':<10} | {'Ozon':>10} | {'ABS-по-записи':>15} | {'SUM-со-знаком':>15}")
print("-" * 80)

tot_abs = 0
tot_signed = 0

for month in OZON:
    our_abs = compute(month, use_abs_per_row=True)
    our_signed = compute(month, use_abs_per_row=False)
    for key in ("fulfil", "agents", "fbo", "other", "marketing"):
        oz = OZON[month][key]
        a = our_abs.get(key, 0)
        s = our_signed.get(key, 0)
        da = a - oz
        ds = s - oz
        flag = ""
        if abs(ds) < 500 and abs(da) >= 500: flag = "  ← signed лучше"
        elif abs(da) < 500 and abs(ds) >= 500: flag = "  ← abs лучше"
        elif abs(ds) < 500: flag = "  ✓✓ оба"
        print(f"{month:<10} | {key:<10} | {oz:>10,.0f} | {a:>15,.0f} | {s:>15,.0f}{flag}")
        tot_abs += abs(da)
        tot_signed += abs(ds)
    print("-" * 80)

print()
print(f"Сумма |Δ| ABS-по-записи: {tot_abs:>12,.0f}")
print(f"Сумма |Δ| SUM-со-знаком: {tot_signed:>12,.0f}")

con.close()
