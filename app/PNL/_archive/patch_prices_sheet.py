"""
patch_prices_sheet.py — добавляет лист ЦЕНЫ в sheets_sync.py.
"""
src = open("sheets_sync.py", encoding="utf-8").read()

if "def sync_prices" in src:
    print("[i] sync_prices уже есть")
    exit(0)

new_block = '''
# ============ ЛИСТ ЦЕНЫ ============
def build_prices(con):
    """Тянет актуальные цены из Ozon API + себестоимость + расчёт маржи."""
    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    date_from = (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")

    rows = con.execute("""
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
    """, (date_from,)).fetchall()

    items = []
    for r in rows:
        price = r[1] or 0
        cost = r[7] or 0
        # Прибыль на единицу (до налога): цена × (1 − комиссия − услуги) − себест
        unit_profit = price * (1 - COMMISSION_PCT - SERVICES_PCT) - cost
        unit_margin = unit_profit / price if price else 0

        # Приоритет сортировки: RED → YELLOW → GREEN/SUPER → WITHOUT
        color = r[3] or "WITHOUT_INDEX"
        if color == "RED":
            priority = 0
        elif color == "YELLOW":
            priority = 1
        elif color in ("GREEN", "SUPER"):
            priority = 2
        else:
            priority = 3

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
            "priority": priority,
        })

    # Сортировка: приоритет → убыточные/низкая маржа → выручка
    items.sort(key=lambda x: (x["priority"], x["unit_margin"], -x["rev_30d"]))

    # Лимит: показываем топ-400
    items = items[:400]

    # Сводка
    from collections import Counter
    colors = Counter(i["color"] for i in items)
    total = len(items)
    red_count = colors.get("RED", 0)
    loss_count = sum(1 for i in items if i["unit_profit"] < 0)

    data = [
        ["ЦЕНЫ — актуальные из Ozon API", "", "", "", "", "", "", ""],
        [f"всего SKU: {total}  |  🔴 RED (дорого рынку): {red_count}  |  "
         f"убыточных на единицу: {loss_count}  |  обновлено {datetime.now().strftime('%H:%M')}",
         "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", ""],
    ]

    # Сводка по индексам
    data.append(["ИНДЕКС ЦЕНЫ (как Ozon видит вас на рынке)", "", "", "", "", "", "", ""])
    data.append(["Индекс", "SKU", "Значит", "", "", "", "", ""])
    color_help = {
        "RED": "дороже рынка — клиенты уходят",
        "YELLOW": "средняя цена",
        "GREEN": "хорошая цена",
        "SUPER": "самый дешёвый — можно поднять",
        "WITHOUT_INDEX": "Ozon не сравнивает",
    }
    for c in ["RED", "YELLOW", "GREEN", "SUPER", "WITHOUT_INDEX"]:
        if colors.get(c, 0) > 0:
            data.append([c, colors[c], color_help.get(c, ""), "", "", "", "", ""])
    data.append(["", "", "", "", "", "", "", ""])

    # Таблица
    data.append(["Offer ID", "Название", "Себест", "Цена Ozon", "Min",
                 "Индекс", "Приб/ед", "Оценка"])

    for it in items:
        # Оценка
        if it["unit_profit"] < 0:
            verdict = "❌ Убыток"
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
            verdict,
        ])

    return data, items


def format_prices(ws, items):
    sid = ws.id
    ops = []

    ops.append({"type": "unmerge", "range": "A1:Z500"})
    ops.append({"type": "clear_notes", "range": "A1:Z500"})

    # Заголовок A1:H1
    ops.append({"type": "merge", "range": "A1:H1"})
    ops.append({"type": "format", "range": "A1:H1", "format": FMT_TITLE})
    ops.append({"type": "row_height", "row": 1, "height": 40})

    # Подзаголовок A2:H2
    sub_fmt = CellFormat(
        textFormat=TextFormat(fontSize=11, italic=True, foregroundColor=Color(0.35, 0.35, 0.35)),
        backgroundColor=SUBHEADER_BG,
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "merge", "range": "A2:H2"})
    ops.append({"type": "format", "range": "A2:H2", "format": sub_fmt})
    ops.append({"type": "row_height", "row": 2, "height": 26})

    # Заголовок сводки по индексам A4:H4
    ops.append({"type": "merge", "range": "A4:H4"})
    ops.append({"type": "format", "range": "A4:H4", "format": FMT_SUBHEADER})
    ops.append({"type": "row_height", "row": 4, "height": 26})

    # Заголовки сводки A5:H5
    tbl_hdr = CellFormat(
        backgroundColor=HEADER_BG,
        textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=HEADER_FG),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "format", "range": "A5:H5", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 5, "height": 32})

    # Цвета индексов
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

    # Сводка 6-10
    order = ["RED", "YELLOW", "GREEN", "SUPER", "WITHOUT_INDEX"]
    colors_present = {}
    for it in items:
        colors_present[it["color"]] = colors_present.get(it["color"], 0) + 1

    row = 6
    for c in order:
        if colors_present.get(c, 0) > 0:
            fmt = color_fmt.get(c, body_center_default())
            ops.append({"type": "format", "range": f"A{row}", "format": fmt})
            ops.append({"type": "format", "range": f"B{row}", "format": fmt})
            ops.append({"type": "format", "range": f"C{row}", "format": CellFormat(
                textFormat=TextFormat(fontSize=10, italic=True, foregroundColor=MUTED_FG),
                horizontalAlignment='LEFT',
            )})
            ops.append({"type": "row_height", "row": row, "height": 26})
            row += 1

    # Таблица начинается после пустой строки
    table_start = row + 1

    ops.append({"type": "format", "range": f"A{table_start}:H{table_start}", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": table_start, "height": 32})

    # Данные
    body_center = CellFormat(textFormat=TextFormat(fontSize=10),
                             horizontalAlignment='CENTER', verticalAlignment='MIDDLE')
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
        # Индекс — цветной
        fmt = color_fmt.get(it["color"], body_center)
        ops.append({"type": "format", "range": f"F{data_row}", "format": fmt})
        # Прибыль — цвет по знаку
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
        # Оценка
        ops.append({"type": "format", "range": f"H{data_row}", "format": body_center})
        ops.append({"type": "row_height", "row": data_row, "height": 24})
        data_row += 1

    # Ширины
    ops.append({"type": "width", "col": "A", "width": 130})
    ops.append({"type": "width", "col": "B", "width": 400})
    ops.append({"type": "width", "col": "C", "width": 90})
    ops.append({"type": "width", "col": "D", "width": 110})
    ops.append({"type": "width", "col": "E", "width": 90})
    ops.append({"type": "width", "col": "F", "width": 140})
    ops.append({"type": "width", "col": "G", "width": 90})
    ops.append({"type": "width", "col": "H", "width": 110})

    ops.append({"type": "frozen", "rows": table_start})

    # Фильтр
    last_row = table_start + len(items)
    ops.append({"type": "filter", "range": f"A{table_start}:H{last_row}"})

    # Примечания
    ops.append({"type": "note", "cell": "F5",
                "note": "Индекс цены Ozon (color_index): RED — дорого рынку, YELLOW — средне, GREEN — хорошо, SUPER — самый дешёвый, WITHOUT_INDEX — Ozon не сравнивает."})
    ops.append({"type": "note", "cell": "G5",
                "note": "Прибыль на единицу = Цена × (1 − комиссия 2,81% − услуги 14,2%) − себестоимость."})
    ops.append({"type": "note", "cell": "H5",
                "note": "❌ Убыток / ⚠ Тонко / ✅ Норма / 🟢 Отлично."})

    n = batch_apply(ws, sid, ops)
    print(f"  Отправлено форматирований одним batch: {n}")


def sync_prices(sh, con):
    print("\\n[Лист ЦЕНЫ]")
    ws = get_or_create_sheet(sh, "ЦЕНЫ")
    data, items = build_prices(con)
    clear_and_write(ws, data)
    print(f"  Записано строк: {len(data)}")
    format_prices(ws, items)


'''

# Вставляем перед def build_money
anchor = "def build_money(con):"
if anchor in src:
    src = src.replace(anchor, new_block + anchor, 1)
    print("[OK] sync_prices добавлена")

# Убираем лишний вызов body_center_default() — заменим на существующий
src = src.replace("body_center_default()", "CellFormat(textFormat=TextFormat(fontSize=10), horizontalAlignment='CENTER')")

# В main — вызываем sync_prices после sync_actions
old_main = '''    # Лист ДЕЛАЙ — со своим форматированием
    sync_actions(sh, con)'''
new_main = '''    # Лист ДЕЛАЙ — со своим форматированием
    sync_actions(sh, con)

    # Лист ЦЕНЫ
    sync_prices(sh, con)'''

if old_main in src:
    src = src.replace(old_main, new_main)
    print("[OK] main обновлён — sync_prices вызывается")

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("\nГотово. Запускай: py sheets_sync.py")
