"""
patch_prices_stock.py — добавляет колонку «Остаток» на лист ЦЕНЫ
и умную оценку с учётом остатка.
"""
src = open("sheets_sync.py", encoding="utf-8").read()

# ============ 1. build_prices — добавить остаток ============
old_query = '''    rows = con.execute("""
        SELECT cp.offer_id, cp.price, cp.min_price, cp.price_index_color,
               cp.price_index_value,
               p.name, p.category_l3, p.cost_price,
               COALESCE(sd.rev, 0)      AS rev_30d,
               COALESCE(sd.orders, 0)   AS orders_30d
        FROM current_prices cp
        JOIN products p ON p.offer_id = cp.offer_id
        LEFT JOIN (
            SELECT sku, SUM(revenue) AS rev, SUM(orders_units) AS orders
            FROM sales_daily WHERE date >= ?
            GROUP BY sku
        ) sd ON sd.sku = p.sku
        WHERE p.is_own = 1 AND p.is_archived = 0
          AND cp.price > 0 AND p.cost_price > 0
    """, (date_from,)).fetchall()'''

new_query = '''    rows = con.execute("""
        SELECT cp.offer_id, cp.price, cp.min_price, cp.price_index_color,
               cp.price_index_value,
               p.name, p.category_l3, p.cost_price,
               COALESCE(sd.rev, 0)      AS rev_30d,
               COALESCE(sd.orders, 0)   AS orders_30d,
               COALESCE(cs.total_present, 0) AS stock
        FROM current_prices cp
        JOIN products p ON p.offer_id = cp.offer_id
        LEFT JOIN current_stocks cs ON cs.offer_id = cp.offer_id
        LEFT JOIN (
            SELECT sku, SUM(revenue) AS rev, SUM(orders_units) AS orders
            FROM sales_daily WHERE date >= ?
            GROUP BY sku
        ) sd ON sd.sku = p.sku
        WHERE p.is_own = 1 AND p.is_archived = 0
          AND cp.price > 0 AND p.cost_price > 0
    """, (date_from,)).fetchall()'''

if old_query in src:
    src = src.replace(old_query, new_query)
    print("[OK] Запрос: добавлен stock")
else:
    print("[?] Не нашёл запрос в build_prices")

# ============ 2. В items — добавить stock + умная сортировка ============
old_items = '''        items.append({
            "offer_id": r[0],
            "name": (r[5] or "")[:60],
            "category": r[6] or "",
            "cost": cost,
            "price": price,
            "min_price": r[2],
            "color": color,
            "idx_value": r[4],
            "unit_profit": unit_profit,
            "unit_margin": unit_margin,
            "rev_30d": r[8] or 0,
            "orders_30d": r[9] or 0,
            "priority": priority,
        })

    # Сортировка: приоритет → убыточные/низкая маржа → выручка
    items.sort(key=lambda x: (x["priority"], x["unit_margin"], -x["rev_30d"]))'''

new_items = '''        stock = r[10] or 0
        # Новая логика приоритетов
        # 0 = RED + есть остаток (реально работаем ценой)
        # 1 = убыточные на единицу (тоже важно)
        # 2 = RED, но нет остатка (заказать или снять)
        # 3 = YELLOW
        # 4 = остальные
        if unit_profit < 0 and stock > 0:
            prio2 = 1
        elif color == "RED" and stock > 0:
            prio2 = 0
        elif color == "RED":
            prio2 = 2
        elif color == "YELLOW":
            prio2 = 3
        else:
            prio2 = 4

        items.append({
            "offer_id": r[0],
            "name": (r[5] or "")[:60],
            "category": r[6] or "",
            "cost": cost,
            "price": price,
            "min_price": r[2],
            "color": color,
            "idx_value": r[4],
            "unit_profit": unit_profit,
            "unit_margin": unit_margin,
            "rev_30d": r[8] or 0,
            "orders_30d": r[9] or 0,
            "stock": stock,
            "priority": prio2,
        })

    # Сортировка: prio → маржа (убыточные наверх)
    items.sort(key=lambda x: (x["priority"], x["unit_margin"]))'''

if old_items in src:
    src = src.replace(old_items, new_items)
    print("[OK] items: добавлен stock + новая сортировка")

# ============ 3. Заголовок таблицы — добавляем Остаток ============
old_hdr = '''    data.append(["Offer ID", "Название", "Себест", "Цена Ozon", "Min",
                 "Индекс", "Приб/ед", "Зак/30д", "Выручка/30д", "Оценка"])'''

new_hdr = '''    data.append(["Offer ID", "Название", "Себест", "Цена Ozon", "Min",
                 "Индекс", "Приб/ед", "Зак/30д", "Выручка/30д", "Остаток", "Оценка"])'''

if old_hdr in src:
    src = src.replace(old_hdr, new_hdr)
    print("[OK] заголовок: + Остаток")

# ============ 4. Логика оценки с учётом остатка ============
old_verdict = '''    for it in items:
        # Умная оценка: маржа + продажи
        orders = it["orders_30d"]
        if it["unit_profit"] < 0:
            verdict = "❌ Убыток"
        elif orders == 0 and it["color"] == "RED":
            verdict = "🔴 Дорого + мёртвый"
        elif orders == 0 and it["unit_margin"] >= 0.15:
            verdict = "🤔 Дорого, не продаётся"
        elif orders == 0:
            verdict = "😴 Нет продаж"
        elif it["unit_margin"] < 0.05:
            verdict = "⚠ Тонко"
        elif it["unit_margin"] < 0.15:
            verdict = "✅ Норма"
        else:
            verdict = "🟢 Отлично"

        profit_str = f"{it['unit_profit']:+,.0f}" if it["unit_profit"] else "0"

        data.append([
            it["offer_id"],
            it["name"],
            f"{it['cost']:,.0f}",
            f"{it['price']:,.0f}",
            f"{it['min_price']:,.0f}" if it["min_price"] else "—",
            it["color"],
            profit_str,
            orders,
            f"{it['rev_30d']:,.0f}" if it["rev_30d"] else "—",
            verdict,
        ])'''

new_verdict = '''    for it in items:
        orders = it["orders_30d"]
        stock = it["stock"]

        # Оценка с учётом остатка
        if it["unit_profit"] < 0 and stock > 0:
            verdict = "❌ Убыток, есть остаток"
        elif it["unit_profit"] < 0:
            verdict = "❌ Убыток (нет товара)"
        elif stock == 0 and it["color"] == "RED":
            verdict = "📦 Закончился, RED"
        elif stock == 0 and it["unit_margin"] >= 0.15:
            verdict = "📦 Закончился, дорого"
        elif stock == 0:
            verdict = "📦 Нет товара"
        elif it["color"] == "RED":
            verdict = "🔴 Дорого + есть остаток"
        elif orders == 0:
            verdict = "😴 Не продаётся"
        elif it["unit_margin"] < 0.05:
            verdict = "⚠ Тонко"
        elif it["unit_margin"] < 0.15:
            verdict = "✅ Норма"
        else:
            verdict = "🟢 Отлично"

        profit_str = f"{it['unit_profit']:+,.0f}" if it["unit_profit"] else "0"

        data.append([
            it["offer_id"],
            it["name"],
            f"{it['cost']:,.0f}",
            f"{it['price']:,.0f}",
            f"{it['min_price']:,.0f}" if it["min_price"] else "—",
            it["color"],
            profit_str,
            orders,
            f"{it['rev_30d']:,.0f}" if it["rev_30d"] else "—",
            stock,
            verdict,
        ])'''

if old_verdict in src:
    src = src.replace(old_verdict, new_verdict)
    print("[OK] Оценка обновлена — учитывает остаток")
else:
    print("[?] Не нашёл блок вердикта")

# ============ 5. format_prices — обновить диапазоны до K ============
src = src.replace('"range": "A1:J1"', '"range": "A1:K1"')
src = src.replace('"range": "A2:J2"', '"range": "A2:K2"')
src = src.replace('"range": "A4:J4"', '"range": "A4:K4"')
src = src.replace('"range": "A5:J5"', '"range": "A5:K5"')
src = src.replace('f"A{table_start}:J{table_start}"', 'f"A{table_start}:K{table_start}"')
src = src.replace('f"A{table_start}:J{last_row}"', 'f"A{table_start}:K{last_row}"')

# В loop данных — H, I, J → H, I, J, K
old_loop = '''        ops.append({"type": "format", "range": f"G{data_row}", "format": profit_fmt})
        # Зак/30д
        orders_val = it["orders_30d"]
        if orders_val == 0:
            order_fmt = CellFormat(textFormat=TextFormat(fontSize=10, italic=True, foregroundColor=MUTED_FG),
                                   horizontalAlignment='CENTER')
        else:
            order_fmt = body_center
        ops.append({"type": "format", "range": f"H{data_row}", "format": order_fmt})
        # Выручка/30д
        ops.append({"type": "format", "range": f"I{data_row}", "format": body_center})
        # Оценка
        ops.append({"type": "format", "range": f"J{data_row}", "format": body_center})
        ops.append({"type": "row_height", "row": data_row, "height": 24})
        data_row += 1'''

new_loop = '''        ops.append({"type": "format", "range": f"G{data_row}", "format": profit_fmt})
        # Зак/30д
        orders_val = it["orders_30d"]
        if orders_val == 0:
            order_fmt = CellFormat(textFormat=TextFormat(fontSize=10, italic=True, foregroundColor=MUTED_FG),
                                   horizontalAlignment='CENTER')
        else:
            order_fmt = body_center
        ops.append({"type": "format", "range": f"H{data_row}", "format": order_fmt})
        # Выручка/30д
        ops.append({"type": "format", "range": f"I{data_row}", "format": body_center})
        # Остаток — цветной
        stock_val = it["stock"]
        if stock_val == 0:
            stock_fmt = CellFormat(textFormat=TextFormat(fontSize=10, italic=True, foregroundColor=MUTED_FG),
                                   horizontalAlignment='CENTER')
        elif stock_val < 3:
            stock_fmt = CellFormat(backgroundColor=WARN_BG,
                                   textFormat=TextFormat(fontSize=10, bold=True, foregroundColor=Color(0.5, 0.4, 0)),
                                   horizontalAlignment='CENTER')
        else:
            stock_fmt = CellFormat(backgroundColor=GOOD_BG,
                                   textFormat=TextFormat(fontSize=10, bold=True, foregroundColor=GOOD_FG),
                                   horizontalAlignment='CENTER')
        ops.append({"type": "format", "range": f"J{data_row}", "format": stock_fmt})
        # Оценка
        ops.append({"type": "format", "range": f"K{data_row}", "format": body_center})
        ops.append({"type": "row_height", "row": data_row, "height": 24})
        data_row += 1'''

if old_loop in src:
    src = src.replace(old_loop, new_loop)
    print("[OK] Loop данных: + Остаток (J), оценка в K")

# Ширины — добавить J и K
old_w = '''    ops.append({"type": "width", "col": "H", "width": 80})
    ops.append({"type": "width", "col": "I", "width": 110})
    ops.append({"type": "width", "col": "J", "width": 150})'''

new_w = '''    ops.append({"type": "width", "col": "H", "width": 80})
    ops.append({"type": "width", "col": "I", "width": 110})
    ops.append({"type": "width", "col": "J", "width": 80})
    ops.append({"type": "width", "col": "K", "width": 180})'''

if old_w in src:
    src = src.replace(old_w, new_w)
    print("[OK] Ширины J/K")

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("\nГотово. Запускай: py sheets_sync.py")
