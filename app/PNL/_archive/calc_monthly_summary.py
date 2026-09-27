"""
calc_monthly_summary.py - PnL из отчёта о реализации.
Формула: delivery − return из /v2/finance/realization.
"""
import os
import sqlite3
import sys

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(APP_DIR, "ozon.db")
TAX_RATE = 0.15

CATEGORY_MAP = {
    32: "Логистика", 59: "Логистика", 98: "Логистика",
    1: "Услуги агентов", 74: "Услуги агентов", 79: "Услуги агентов",
    29: "Услуги агентов", 76: "Услуги агентов", 45: "Услуги агентов",
    3: "Реклама",
    71: "Услуги FBO", 46: "Услуги FBO",
    93: "Другие услуги",
    18: "Прочие", 20: "Прочие",
}


def main():
    month = sys.argv[1] if len(sys.argv) > 1 else "2026-08"

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    # === Из monthly_realization_rows (уже посчитано delivery-return) ===
    r = con.execute("""
        SELECT SUM(sale_price) AS slp, SUM(bonus) AS bonus,
               SUM(coinvestment) AS coinv, SUM(gross_commission) AS comm
        FROM monthly_realization_rows
        WHERE month = ?
    """, (month,)).fetchone()
    sale_price = r["slp"] or 0
    bonus = r["bonus"] or 0
    coinv = r["coinv"] or 0
    commission = r["comm"] or 0

    # === Услуги из accruals_services ===
    y, m = month.split("-")
    date_from = f"{month}-01"
    ny, nm = (int(y) + 1, 1) if int(m) == 12 else (int(y), int(m) + 1)
    date_to = f"{ny}-{nm:02d}-01"

    services = {}
    for row in con.execute("""
        SELECT type_id, SUM(amount) AS total
        FROM accruals_services WHERE date >= ? AND date < ?
        GROUP BY type_id
    """, (date_from, date_to)):
        services[row["type_id"]] = abs(row["total"] or 0)

    cats = {}
    for tid, total in services.items():
        cat = CATEGORY_MAP.get(tid, "Без категории")
        cats[cat] = cats.get(cat, 0) + total

    # === Себестоимость по SKU из realization ===
    real_skus = [row[0] for row in con.execute("""
        SELECT DISTINCT sku FROM monthly_realization_rows WHERE month = ?
    """, (month,))]

    cogs = 0.0
    if real_skus:
        q = ",".join("?" * len(real_skus))
        for row in con.execute(f"""
            SELECT p.cost_price, SUM(sd.delivered) AS d
            FROM sales_daily sd JOIN products p ON p.sku = sd.sku
            WHERE sd.date >= ? AND sd.date < ?
              AND p.sku IN ({q})
            GROUP BY p.sku
        """, (date_from, date_to, *real_skus)):
            cogs += (row[0] or 0) * (row[1] or 0)

    # === Расчёты ===
    revenue = sale_price + bonus + coinv
    services_total = sum(cats.values())
    expenses = commission + services_total
    margin = revenue - expenses - cogs
    tax_base = revenue - bonus
    tax = tax_base * TAX_RATE
    net = margin - tax

    # === Вывод ===
    print()
    print("=" * 60)
    print(f"P&L ЗА {month}")
    print("=" * 60)
    print()
    print(f"  Выручка от реализации:    {sale_price:>14,.2f}")
    print(f"  + Баллы:                  {bonus:>14,.2f}")
    print(f"  + Партнёры:               {coinv:>14,.2f}")
    print(f"  = ВЫРУЧКА:                {revenue:>14,.2f}")
    print()
    print(f"  Комиссия Ozon:            {commission:>14,.2f}")
    for cat in ["Логистика", "Услуги агентов", "Услуги FBO",
                "Другие услуги", "Прочие", "Реклама", "Без категории"]:
        if cats.get(cat):
            print(f"  {cat:<25} {cats[cat]:>14,.2f}")
    print(f"  = РАСХОДЫ:                {expenses:>14,.2f}")
    print()
    print(f"  СЕБЕСТОИМОСТЬ:            {cogs:>14,.2f}")
    print()
    print(f"  МАРЖА:                    {margin:>14,.2f}")
    print(f"  Налоговая база:           {tax_base:>14,.2f}")
    print(f"  Налог УСН 15%:            {tax:>14,.2f}")
    print(f"  ЧИСТАЯ ПРИБЫЛЬ:           {net:>14,.2f}")

    con.close()


if __name__ == "__main__":
    main()
