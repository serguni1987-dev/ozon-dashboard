import re
src = open("daily_dashboard.py", encoding="utf-8").read()

# ---- Патч 1: формула целевой цены ----
pat1 = re.compile(
    r"need_price = \(m\['cost_price'\].*?else 0"
)
new1 = ("denom = 1 - COMMISSION_PCT - SERVICES_PCT - MARGIN_LOW\n"
        "            need_price = (m['cost_price'] / denom) if (denom > 0 and m['orders']) else 0")
src, n1 = pat1.subn(new1, src)
print(f"Патч 1 (формула): {'OK' if n1 else 'НЕ НАЙДЕН'}")

# ---- Патч 2: активные SKU только с заказами ----
old2 = "SELECT SUM(revenue), SUM(orders_units), COUNT(DISTINCT sku)"
new2 = ("SELECT SUM(revenue), SUM(orders_units),\n"
        "               SUM(CASE WHEN orders_units > 0 THEN 1 ELSE 0 END)")
if old2 in src:
    src = src.replace(old2, new2)
    print("Патч 2 (активные SKU): OK")
else:
    print("Патч 2: НЕ НАЙДЕН")

# ---- Патч 3: полная статистика мёртвых ----
pat3 = re.compile(
    r"    dead = con\.execute.*?print\(\"    нет\"\)\n",
    re.DOTALL
)
new3 = '''    dead_all = con.execute("""
        SELECT p.offer_id, p.name, SUM(sd.views_total) AS views,
               SUM(sd.orders_units) AS orders
        FROM sales_daily sd
        JOIN products p ON p.sku = sd.sku
        WHERE sd.date BETWEEN ? AND ?
          AND p.is_own = 1
        GROUP BY p.sku
        HAVING views >= ? AND orders <= ?
        ORDER BY views DESC
    """, (month_ago, max_date, DEAD_VIEWS_MIN, DEAD_ORDERS_MAX)).fetchall()
    print(f"\\n  [4] МЁРТВЫЕ (показов >= {DEAD_VIEWS_MIN}, заказов 0)")
    if dead_all:
        total_waste = sum(r[2] for r in dead_all)
        print(f"    Всего SKU: {len(dead_all)}, показов впустую: {total_waste:,}")
        print(f"    Топ-10 по показам:")
        for offer_id, name, views, orders in dead_all[:10]:
            print(f"      {offer_id:<18} {name[:40]:<40} показов {views:>6}")
    else:
        print("    нет")
'''
src, n3 = pat3.subn(new3, src)
print(f"Патч 3 (мёртвые): {'OK' if n3 else 'НЕ НАЙДЕН'}")

open("daily_dashboard.py", "w", encoding="utf-8").write(src)
print("\nФайл обновлён. Запускайте: py daily_dashboard.py")
