"""
fix_cogs_formula.py — меняем формулу себестоимости в calc_monthly_summary.py.
Было: orders_units × cost_price  (заказано)
Стало: delivered × cost_price    (доставлено)
"""
src = open("calc_monthly_summary.py", encoding="utf-8").read()

old = '''    # === 4. Себестоимость ===
    cogs = 0.0
    for row in con.execute("""
        SELECT p.cost_price, SUM(sd.orders_units) AS orders
        FROM sales_daily sd
        JOIN products p ON p.sku = sd.sku
        WHERE sd.date >= ? AND sd.date < ?
        GROUP BY p.sku
    """, (date_from, date_to)):
        cogs += (row[0] or 0) * (row[1] or 0)'''

new = '''    # === 4. Себестоимость — по ДОСТАВЛЕННЫМ ===
    cogs = 0.0
    for row in con.execute("""
        SELECT p.cost_price, SUM(sd.delivered) AS delivered
        FROM sales_daily sd
        JOIN products p ON p.sku = sd.sku
        WHERE sd.date >= ? AND sd.date < ?
        GROUP BY p.sku
    """, (date_from, date_to)):
        cogs += (row[0] or 0) * (row[1] or 0)

    # Для сравнения — себестоимость по заказам
    cogs_orders = 0.0
    for row in con.execute("""
        SELECT p.cost_price, SUM(sd.orders_units) AS orders
        FROM sales_daily sd
        JOIN products p ON p.sku = sd.sku
        WHERE sd.date >= ? AND sd.date < ?
        GROUP BY p.sku
    """, (date_from, date_to)):
        cogs_orders += (row[0] or 0) * (row[1] or 0)

    # И по выкупленным
    cogs_purchased = 0.0
    for row in con.execute("""
        SELECT p.cost_price, SUM(sd.purchased) AS purchased
        FROM sales_daily sd
        JOIN products p ON p.sku = sd.sku
        WHERE sd.date >= ? AND sd.date < ?
        GROUP BY p.sku
    """, (date_from, date_to)):
        cogs_purchased += (row[0] or 0) * (row[1] or 0)'''

if old in src:
    src = src.replace(old, new)
    print("[OK] Формула себестоимости изменена")
else:
    print("[?] Не нашёл блок себестоимости")

# В выводе — добавить сравнение трёх вариантов
old2 = '''    print(f"\\n[4] СЕБЕСТОИМОСТЬ И МАРЖА")
    print(f"    Себестоимость:                 {money(cogs)}")'''

new2 = '''    print(f"\\n[4] СЕБЕСТОИМОСТЬ И МАРЖА")
    print(f"    COGS по заказам (orders):      {money(cogs_orders)}")
    print(f"    COGS по доставленным:          {money(cogs)}")
    print(f"    COGS по выкупленным:           {money(cogs_purchased)}")
    print(f"    ⭐ Используем (доставлено):    {money(cogs)}")'''

if old2 in src:
    src = src.replace(old2, new2)
    print("[OK] Вывод обновлён")

open("calc_monthly_summary.py", "w", encoding="utf-8").write(src)
print()
print("Готово. Запускай: py calc_monthly_summary.py 2026-08")
