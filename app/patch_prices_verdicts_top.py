"""
patch_prices_verdicts_top.py — перемещает блок ВЫВОДЫ наверх листа ЦЕНЫ.
Новая структура:
  1: заголовок
  2: подзаголовок
  3: пусто
  4: "ИНДЕКС ЦЕНЫ"
  5: заголовки сводки
  6-10: сводка (5 строк)
  11: пусто
  12: ВЫВОДЫ
  13-18: тезисы (6 строк)
  19: пусто
  20: заголовки таблицы SKU
  21+: SKU
"""
import re

src = open("sheets_sync.py", encoding="utf-8").read()

# === Новый build_prices ===
new_build = '''def build_prices(con):
    """Тянет актуальные цены из Ozon API + себестоимость + расчёт маржи."""
    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    date_from = (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")

    rows = con.execute("""
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
    """, (date_from,)).fetchall()

    items = []
    for r in rows:
        price = r[1] or 0
        cost = r[7] or 0
        unit_profit = price * (1 - COMMISSION_PCT - SERVICES_PCT) - cost
        unit_margin = unit_profit / price if price else 0

        color = r[3] or "WITHOUT_INDEX"
        stock = r[10] or 0

        # Приоритет сортировки
        if unit_profit < 0 and stock > 0:
            prio2 = 0
        elif color == "RED" and stock > 0:
            prio2 = 1
        elif unit_profit < 0:
            prio2 = 2
        elif color == "RED":
            prio2 = 3
        elif color == "YELLOW":
            prio2 = 4
        else:
            prio2 = 5

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

    items.sort(key=lambda x: (x["priority"], x["unit_margin"]))
    items = items[:400]

    from collections import Counter
    colors = Counter(i["color"] for i in items)
    total = len(items)
    red_total = colors.get("RED", 0)
    red_with_stock = sum(1 for i in items if i["color"] == "RED" and i["stock"] > 0)
    red_no_stock = red_total - red_with_stock
    loss_with_stock = sum(1 for i in items if i["unit_profit"] < 0 and i["stock"] > 0)
    loss_no_stock = sum(1 for i in items if i["unit_profit"] < 0 and i["stock"] == 0)
    yellow_no_stock = sum(1 for i in items if i["color"] == "YELLOW" and i["stock"] == 0)
    super_total = sum(1 for i in items if i["color"] == "SUPER")
    super_with_stock = sum(1 for i in items if i["color"] == "SUPER" and i["stock"] > 0)
    active_red = sum(1 for i in items if i["color"] == "RED" and i["orders_30d"] > 0)

    # === Формируем data ===
    data = []
    data.append(["ЦЕНЫ — актуальные из Ozon API", "", "", "", "", "", "", "", "", "", ""])
    data.append([f"всего SKU: {total}  |  🔴 RED: {red_total}  |  "
                 f"с остатком: {sum(1 for i in items if i['stock'] > 0)}  |  "
                 f"обновлено {datetime.now().strftime('%H:%M')}",
                 "", "", "", "", "", "", "", "", "", ""])
    data.append(["", "", "", "", "", "", "", "", "", "", ""])

    # Сводка по индексам
    data.append(["ИНДЕКС ЦЕНЫ (как Ozon видит вас на рынке)", "", "", "", "", "", "", "", "", "", ""])
    data.append(["Индекс", "SKU", "Значит", "", "", "", "", "", "", "", ""])
    color_help = {
        "RED": "дороже рынка — клиенты уходят",
        "YELLOW": "средняя цена",
        "GREEN": "хорошая цена",
        "SUPER": "самый дешёвый — можно поднять",
        "WITHOUT_INDEX": "Ozon не сравнивает",
    }
    for c in ["RED", "YELLOW", "GREEN", "SUPER", "WITHOUT_INDEX"]:
        if colors.get(c, 0) > 0:
            data.append([c, colors[c], color_help.get(c, ""), "", "", "", "", "", "", "", ""])
    data.append(["", "", "", "", "", "", "", "", "", "", ""])

    # === ВЫВОДЫ (до таблицы SKU!) ===
    data.append(["ВЫВОДЫ", "", "", "", "", "", "", "", "", "", ""])

    if red_total > 100:
        v1 = f"❌ {red_total} SKU в RED (дорого рынку) — но {red_no_stock} из них без остатка, это не проблема цены"
    elif red_total > 30:
        v1 = f"⚠ {red_total} SKU в RED — стоит проверить цены"
    else:
        v1 = f"✅ Мало RED SKU ({red_total}) — цены в норме"

    real_problems = red_with_stock + loss_with_stock
    if real_problems > 0:
        v2 = (f"→ Реальных проблем цены: {real_problems} SKU  "
              f"(RED с остатком: {red_with_stock}, убыточных с остатком: {loss_with_stock})  "
              f"— работать через apply_prices.py")
    else:
        v2 = "→ Реальных проблем цены нет — все RED/убыточные без остатка"

    no_stock = red_no_stock + yellow_no_stock + loss_no_stock
    if no_stock > 50:
        v3 = f"📦 {no_stock} SKU закончились — решить: заказать или архивировать"
    elif no_stock > 0:
        v3 = f"📦 {no_stock} SKU закончились — проверить, нужны ли"
    else:
        v3 = "✅ Все SKU с остатком"

    if super_with_stock > 0:
        v4 = f"💰 {super_with_stock} SKU в SUPER (дешевле рынка) с остатком — можно поднять цену"
    elif super_total > 0:
        v4 = f"ℹ {super_total} SKU в SUPER — все без остатка"
    else:
        v4 = "ℹ Нет SKU в SUPER"

    v5 = ""
    if active_red > 0:
        v5 = (f"🔥 {active_red} SKU в RED, но всё равно продаются — "
              f"клиенты готовы платить дороже рынка")

    if real_problems == 0:
        v6 = "→ ИТОГ: с ценами работать не нужно — проблема в ассортименте и остатках"
    elif real_problems < 10:
        v6 = "→ ИТОГ: точечно поправить цены у 1–10 SKU через apply_prices.py"
    else:
        v6 = "→ ИТОГ: массовая коррекция цен через apply_prices.py даст эффект"

    data.append(["", v1, "", "", "", "", "", "", "", "", ""])
    data.append(["", v2, "", "", "", "", "", "", "", "", ""])
    data.append(["", v3, "", "", "", "", "", "", "", "", ""])
    data.append(["", v4, "", "", "", "", "", "", "", "", ""])
    if v5:
        data.append(["", v5, "", "", "", "", "", "", "", "", ""])
    data.append(["", v6, "", "", "", "", "", "", "", "", ""])

    data.append(["", "", "", "", "", "", "", "", "", "", ""])

    # === Таблица SKU ===
    data.append(["Offer ID", "Название", "Себест", "Цена Ozon", "Min",
                 "Индекс", "Приб/ед", "Зак/30д", "Выручка/30д", "Остаток", "Оценка"])

    for it in items:
        orders = it["orders_30d"]
        stock = it["stock"]

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
        ])

    return data, items, len([v for v in [v1, v2, v3, v4, v5, v6] if v])
'''

pattern = re.compile(r"def build_prices\(con\):.*?(?=\ndef format_prices)", re.DOTALL)
src, n = pattern.subn(new_build + "\n\n", src)
print(f"[{'OK' if n else 'FAIL'}] build_prices переписан (выводы наверху)")

# === Новый format_prices ===
new_format = '''def format_prices(ws, items, n_verdicts=6):
    sid = ws.id
    ops = []

    ops.append({"type": "unmerge", "range": "A1:Z500"})
    ops.append({"type": "clear_notes", "range": "A1:Z500"})

    # Заголовок
    ops.append({"type": "merge", "range": "A1:K1"})
    ops.append({"type": "format", "range": "A1:K1", "format": FMT_TITLE})
    ops.append({"type": "row_height", "row": 1, "height": 40})

    # Подзаголовок
    sub_fmt = CellFormat(
        textFormat=TextFormat(fontSize=11, italic=True, foregroundColor=Color(0.35, 0.35, 0.35)),
        backgroundColor=SUBHEADER_BG,
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "merge", "range": "A2:K2"})
    ops.append({"type": "format", "range": "A2:K2", "format": sub_fmt})
    ops.append({"type": "row_height", "row": 2, "height": 26})

    # Сводка по индексам
    ops.append({"type": "merge", "range": "A4:K4"})
    ops.append({"type": "format", "range": "A4:K4", "format": FMT_SUBHEADER})
    ops.append({"type": "row_height", "row": 4, "height": 26})

    # Заголовки сводки
    tbl_hdr = CellFormat(
        backgroundColor=HEADER_BG,
        textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=HEADER_FG),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "format", "range": "A5:C5", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 5, "height": 32})

    color_fmt = {
        "RED":          CellFormat(backgroundColor=BAD_BG,
                                   textFormat=TextFormat(bold=True, foregroundColor=BAD_FG),
                                   horizontalAlignment='CENTER'),
        "YELLOW":       CellFormat(backgroundColor=WARN_BG,
                                   textFormat=TextFormat(bold=True, foregroundColor=Color(0.5, 0.4, 0)),
                                   horizontalAlignment='CENTER'),
        "GREEN":        CellFormat(backgroundColor=GOOD_BG,
                                   textFormat=TextFormat(bold=True, foregroundColor=GOOD_FG),
                                   horizontalAlignment='CENTER'),
        "SUPER":        CellFormat(backgroundColor=Color(0.85, 0.95, 0.85),
                                   textFormat=TextFormat(bold=True, foregroundColor=Color(0.1, 0.45, 0.1)),
                                   horizontalAlignment='CENTER'),
        "WITHOUT_INDEX":CellFormat(textFormat=TextFormat(fontSize=10, italic=True,
                                                         foregroundColor=MUTED_FG),
                                   horizontalAlignment='CENTER'),
    }
    body_center = CellFormat(textFormat=TextFormat(fontSize=10),
                             horizontalAlignment='CENTER', verticalAlignment='MIDDLE')

    # Строки 6-10 сводки
    order = ["RED", "YELLOW", "GREEN", "SUPER", "WITHOUT_INDEX"]
    colors_present = {}
    for it in items:
        colors_present[it["color"]] = colors_present.get(it["color"], 0) + 1

    row = 6
    for c in order:
        if colors_present.get(c, 0) > 0:
            fmt = color_fmt.get(c, body_center)
            ops.append({"type": "format", "range": f"A{row}", "format": fmt})
            ops.append({"type": "format", "range": f"B{row}", "format": fmt})
            ops.append({"type": "format", "range": f"C{row}", "format": CellFormat(
                textFormat=TextFormat(fontSize=10, italic=True, foregroundColor=MUTED_FG),
                horizontalAlignment='LEFT',
            )})
            ops.append({"type": "row_height", "row": row, "height": 26})
            row += 1

    # === ВЫВОДЫ ===
    verdict_hdr_row = row + 1  # пустая строка после сводки
    ops.append({"type": "merge", "range": f"B{verdict_hdr_row}:K{verdict_hdr_row}"})
    ops.append({"type": "format", "range": f"B{verdict_hdr_row}:K{verdict_hdr_row}",
                "format": FMT_SUBHEADER})
    ops.append({"type": "row_height", "row": verdict_hdr_row, "height": 26})

    for i in range(n_verdicts):
        r = verdict_hdr_row + 1 + i
        ops.append({"type": "merge", "range": f"B{r}:K{r}"})
        ops.append({"type": "row_height", "row": r, "height": 30})

    # === Таблица SKU ===
    table_start = verdict_hdr_row + n_verdicts + 2  # +1 пустая

    ops.append({"type": "format", "range": f"A{table_start}:K{table_start}", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": table_start, "height": 32})

    # Данные
    body_left = CellFormat(textFormat=TextFormat(fontSize=10),
                           horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
                           wrapStrategy='CLIP')
    body_offer = CellFormat(textFormat=TextFormat(fontSize=10, bold=True),
                            horizontalAlignment='CENTER')
    body_price = CellFormat(textFormat=TextFormat(fontSize=11, bold=True),
                            horizontalAlignment='CENTER')

    data_row = table_start + 1
    for it in items:
        ops.append({"type": "format", "range": f"A{data_row}", "format": body_offer})
        ops.append({"type": "format", "range": f"B{data_row}", "format": body_left})
        ops.append({"type": "format", "range": f"C{data_row}", "format": body_center})
        ops.append({"type": "format", "range": f"D{data_row}", "format": body_price})
        ops.append({"type": "format", "range": f"E{data_row}", "format": body_center})
        fmt = color_fmt.get(it["color"], body_center)
        ops.append({"type": "format", "range": f"F{data_row}", "format": fmt})
        if it["unit_profit"] < 0:
            profit_fmt = CellFormat(backgroundColor=BAD_BG,
                                    textFormat=TextFormat(fontSize=10, bold=True, foregroundColor=BAD_FG),
                                    horizontalAlignment='CENTER')
        elif it["unit_margin"] < 0.05:
            profit_fmt = CellFormat(backgroundColor=WARN_BG,
                                    textFormat=TextFormat(fontSize=10, bold=True, foregroundColor=Color(0.5, 0.4, 0)),
                                    horizontalAlignment='CENTER')
        else:
            profit_fmt = CellFormat(textFormat=TextFormat(fontSize=10, bold=True),
                                    horizontalAlignment='CENTER')
        ops.append({"type": "format", "range": f"G{data_row}", "format": profit_fmt})
        orders_val = it["orders_30d"]
        if orders_val == 0:
            order_fmt = CellFormat(textFormat=TextFormat(fontSize=10, italic=True, foregroundColor=MUTED_FG),
                                   horizontalAlignment='CENTER')
        else:
            order_fmt = body_center
        ops.append({"type": "format", "range": f"H{data_row}", "format": order_fmt})
        ops.append({"type": "format", "range": f"I{data_row}", "format": body_center})
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
        ops.append({"type": "format", "range": f"K{data_row}", "format": body_center})
        ops.append({"type": "row_height", "row": data_row, "height": 24})
        data_row += 1

    # Ширины
    ops.append({"type": "width", "col": "A", "width": 130})
    ops.append({"type": "width", "col": "B", "width": 380})
    ops.append({"type": "width", "col": "C", "width": 80})
    ops.append({"type": "width", "col": "D", "width": 100})
    ops.append({"type": "width", "col": "E", "width": 90})
    ops.append({"type": "width", "col": "F", "width": 130})
    ops.append({"type": "width", "col": "G", "width": 90})
    ops.append({"type": "width", "col": "H", "width": 80})
    ops.append({"type": "width", "col": "I", "width": 110})
    ops.append({"type": "width", "col": "J", "width": 80})
    ops.append({"type": "width", "col": "K", "width": 180})

    ops.append({"type": "frozen", "rows": table_start})

    # Фильтр
    last_row = table_start + len(items)
    ops.append({"type": "filter", "range": f"A{table_start}:K{last_row}"})

    # Примечания
    ops.append({"type": "note", "cell": "F5",
                "note": "Индекс цены Ozon: RED — дорого, YELLOW — средне, GREEN — хорошо, SUPER — самый дешёвый, WITHOUT_INDEX — Ozon не сравнивает."})
    ops.append({"type": "note", "cell": "G5",
                "note": "Прибыль на единицу = Цена × (1 − комиссия − услуги) − себестоимость."})
    ops.append({"type": "note", "cell": "J5",
                "note": "Остаток актуальный из Ozon API."})

    n = batch_apply(ws, sid, ops)
    print(f"  Отправлено форматирований одним batch: {n}")

    # Цвет выводов
    try:
        vals = ws.get(f"B{verdict_hdr_row + 1}:B{verdict_hdr_row + n_verdicts}")
        ops2 = []
        for i, row_v in enumerate(vals):
            if not row_v:
                continue
            v = row_v[0]
            r = verdict_hdr_row + 1 + i
            if v.startswith("❌") or v.startswith("⚠"):
                bg, fg = BAD_BG, BAD_FG
            elif v.startswith("✅") or v.startswith("🟢"):
                bg, fg = GOOD_BG, GOOD_FG
            elif v.startswith("→ ИТОГ"):
                bg, fg = Color(0.90, 0.94, 1.0), Color(0.10, 0.20, 0.50)
            elif v.startswith("→"):
                bg, fg = Color(0.90, 0.94, 1.0), Color(0.10, 0.20, 0.50)
            elif v.startswith("💰"):
                bg, fg = Color(0.95, 0.95, 0.75), Color(0.5, 0.4, 0)
            else:
                bg, fg = SUBHEADER_BG, Color(0.2, 0.2, 0.2)
            ops2.append({"type": "format", "range": f"B{r}:K{r}", "format": CellFormat(
                backgroundColor=bg,
                textFormat=TextFormat(fontSize=11, foregroundColor=fg),
                horizontalAlignment='LEFT', verticalAlignment='MIDDLE', wrapStrategy='WRAP',
            )})
        if ops2:
            n2 = batch_apply(ws, sid, ops2)
            print(f"  Цвет выводов: {n2}")
    except Exception as e:
        print(f"  [WARN] Цвет выводов: {e}")
'''

pattern = re.compile(r"def format_prices\(ws, items.*?\Z", re.DOTALL)
src, n = pattern.subn(new_format, src)
print(f"[{'OK' if n else 'FAIL'}] format_prices переписан")

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("\nГотово. Запускай: py sheets_sync.py")
