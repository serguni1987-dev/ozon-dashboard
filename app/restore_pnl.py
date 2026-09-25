"""
restore_pnl.py - откат sync_pnl.py к рабочей версии:
- Только месяцы с realization
- Себестоимость = delivered × cost по SKU из realization
- Сентябрь не показываем (ждём отчёт)
"""
import re

# === Патч 1: get_all_months — только месяцы с realization ===
src = open("sync_pnl.py", encoding="utf-8").read()

old1 = '''def get_all_months():
    con = sqlite3.connect(DB)
    months = set()
    for r in con.execute("SELECT DISTINCT month FROM monthly_realization_rows"):
        months.add(r[0])
    for r in con.execute("SELECT DISTINCT substr(date, 1, 7) AS m FROM accruals"):
        months.add(r[0])
    con.close()
    return sorted(months)'''

new1 = '''def get_all_months():
    """Только месяцы с realization (отчёт о реализации уже пришёл)."""
    con = sqlite3.connect(DB)
    months = [r[0] for r in con.execute(
        "SELECT DISTINCT month FROM monthly_realization_rows ORDER BY month"
    )]
    con.close()
    return months'''

if old1 in src:
    src = src.replace(old1, new1)
    print("[OK] get_all_months: только месяцы с realization")
else:
    print("[?] Не нашёл get_all_months")

# === Патч 2: себестоимость — простая формула ===
idx = src.find("# === Себестоимость")
if idx < 0:
    idx = src.find("cogs = 0.0")
    print(f"[i] Ищу по 'cogs = 0.0', idx={idx}")

end = src.find("revenue = sale_price + bonus", idx)
if idx > 0 and end > idx:
    new_block = '''# === Себестоимость ===
    # delivered × cost_price по SKU из realization
    cogs = 0.0
    real_skus = [r[0] for r in con.execute("""
        SELECT DISTINCT sku FROM monthly_realization_rows WHERE month = ?
    """, (month,))]

    if real_skus:
        q = ",".join("?" * len(real_skus))
        for row in con.execute(f"""
            SELECT p.cost_price, SUM(sd.delivered) AS d
            FROM sales_daily sd JOIN products p ON p.sku = sd.sku
            WHERE sd.date >= ? AND sd.date < ? AND p.sku IN ({q})
            GROUP BY p.sku
        """, (d1, d2, *real_skus)):
            cogs += f(row[0]) * f(row[1])

    '''
    src = src[:idx] + new_block + src[end:]
    print("[OK] Себестоимость: delivered × cost по SKU realization")
else:
    print(f"[?] Не нашёл блок себестоимости")

open("sync_pnl.py", "w", encoding="utf-8").write(src)
print("Готово.")
