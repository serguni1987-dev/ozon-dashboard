src = open("add_decision.py", encoding="utf-8").read()

old = """    agg = con.execute(\"\"\"
        SELECT SUM(revenue) AS rev, SUM(orders_units) AS orders,
               SUM(views_total) AS views, SUM(cart_adds_total) AS carts,
               AVG(avg_price) AS avg_price
        FROM sales_daily
        WHERE sku = ? AND date BETWEEN ? AND ?
    \"\"\", (prod[\"sku\"], date_from, max_date)).fetchone()"""

new = """    agg = con.execute(\"\"\"
        SELECT SUM(revenue) AS rev, SUM(orders_units) AS orders,
               SUM(views_total) AS views, SUM(cart_adds_total) AS carts
        FROM sales_daily
        WHERE sku = ? AND date BETWEEN ? AND ?
    \"\"\", (prod[\"sku\"], date_from, max_date)).fetchone()

    # Средняя цена — только по дням с заказами, иначе нули занижают
    price_row = con.execute(\"\"\"
        SELECT AVG(avg_price) AS p FROM sales_daily
        WHERE sku = ? AND date BETWEEN ? AND ? AND orders_units > 0
    \"\"\", (prod[\"sku\"], date_from, max_date)).fetchone()
    avg_price = price_row[\"p\"] if price_row else None"""

if old in src:
    src = src.replace(old, new)
    src = src.replace('price_before = agg["avg_price"] or 0', 'price_before = avg_price or 0')
    open("add_decision.py", "w", encoding="utf-8").write(src)
    print("[OK] Патч применён")
else:
    print("[?] Не нашёл место. Патчим вручную: замени AVG(avg_price) на подзапрос с orders_units > 0")
