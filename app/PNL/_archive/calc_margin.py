"""
calc_margin.py — маржа по SKU с реальными ставками Ozon.
Ставки берутся из accruals (реальные начисления), применяются ко всей выручке.
"""
import sqlite3

COMMISSION_PCT = 0.0281   # эффективная комиссия (после компенсации баллами)
SERVICES_PCT   = 0.142    # логистика, возвраты, эквайринг и прочее
TAX_PCT        = 0.15

DB = "ozon.db"


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    # Проверим ставки: реальные из accruals
    cov = con.execute("""
        SELECT SUM(sale_price) AS slp,
               SUM(sale_commission) AS comm,
               SUM(bonus) AS bonus,
               SUM(coinvestment) AS ci
        FROM accruals
    """).fetchone()
    if cov and cov["slp"]:
        eff_rate = (cov["comm"] + cov["bonus"] + cov["ci"]) / cov["slp"]
        print(f"[проверка] Реальная эфф. комиссия / sale_price: {eff_rate*100:.2f}%")

    svc = con.execute("SELECT SUM(amount) AS s FROM accruals_services").fetchone()
    if svc and cov and cov["slp"]:
        svc_rate = abs(svc["s"]) / cov["slp"]
        print(f"[проверка] Услуги Ozon / sale_price: {svc_rate*100:.2f}%")
    print()

    rows = con.execute("""
        SELECT p.offer_id, p.name, p.cost_price,
               SUM(sd.revenue)      AS revenue,
               SUM(sd.orders_units) AS orders
        FROM sales_daily sd
        JOIN products p ON p.sku = sd.sku
        WHERE p.is_own = 1 AND p.is_archived = 0 AND sd.orders_units > 0
        GROUP BY p.sku
        ORDER BY revenue DESC
    """).fetchall()

    print("=" * 132)
    print(f"МАРЖА ПО SKU  (комиссия {COMMISSION_PCT*100:.2f}%, услуги {SERVICES_PCT*100:.2f}%, УСН {TAX_PCT*100:.0f}%)")
    print("=" * 132)
    print(f"{'Offer ID':<18} {'Название':<42} {'Выручка':>11} {'Себест':>11} "
          f"{'Комис':>9} {'Услуги':>9} {'Приб':>10} {'Маржа%':>8} {'Зак':>4}")
    print("-" * 132)

    tot = dict(rev=0.0, cost=0.0, comm=0.0, serv=0.0, profit=0.0, orders=0)

    for r in rows:
        rev = r["revenue"] or 0
        orders = r["orders"] or 0
        cost_total = (r["cost_price"] or 0) * orders
        comm = rev * COMMISSION_PCT
        serv = rev * SERVICES_PCT
        pb = rev - cost_total - comm - serv
        tax = pb * TAX_PCT if pb > 0 else 0
        profit = pb - tax
        margin = profit / rev if rev else 0

        tot["rev"] += rev
        tot["cost"] += cost_total
        tot["comm"] += comm
        tot["serv"] += serv
        tot["profit"] += profit
        tot["orders"] += orders

        name = (r["name"] or "")[:41]
        print(f"{r['offer_id']:<18} {name:<42} {rev:>11,.0f} {cost_total:>11,.0f} "
              f"{comm:>9,.0f} {serv:>9,.0f} {profit:>10,.0f} {margin*100:>7.1f}% {orders:>4}")

    print("-" * 132)
    total_margin = tot["profit"] / tot["rev"] * 100 if tot["rev"] else 0
    print(f"{'ИТОГО':<18} {'':<42} {tot['rev']:>11,.0f} {tot['cost']:>11,.0f} "
          f"{tot['comm']:>9,.0f} {tot['serv']:>9,.0f} {tot['profit']:>10,.0f} "
          f"{total_margin:>7.1f}% {tot['orders']:>4}")
    print("=" * 132)

    # Проблемные
    print("\nПРОБЛЕМНЫЕ SKU (маржа < 15%)")
    print("-" * 132)
    problems = []
    for r in rows:
        rev = r["revenue"] or 0
        orders = r["orders"] or 0
        cost_total = (r["cost_price"] or 0) * orders
        comm = rev * COMMISSION_PCT
        serv = rev * SERVICES_PCT
        pb = rev - cost_total - comm - serv
        tax = pb * TAX_PCT if pb > 0 else 0
        profit = pb - tax
        margin = profit / rev if rev else 0
        if margin < 0.15:
            problems.append((margin, r["offer_id"], r["name"], profit))
    problems.sort()
    for margin, oid, name, profit in problems:
        print(f"  {oid:<18} {(name or '')[:55]:<55} маржа {margin*100:>6.1f}%, прибыль {profit:>9,.0f} ₽")

    con.close()


if __name__ == "__main__":
    main()
