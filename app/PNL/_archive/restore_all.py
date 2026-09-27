"""
restore_all.py — восстанавливает пропавшие функции и переделывает ЦЕНЫ под вариант Б.
"""
import re

src = open("sheets_sync.py", encoding="utf-8").read()

# ============ 1. Заменяем build_prices + format_prices на вариант Б ============
pattern = re.compile(
    r"def build_prices\(con\):.*?(?=\n\ndef main\()",
    re.DOTALL
)

new_block = '''def build_prices(con):
    """Лист ЦЕНЫ — только SKU с остатком > 0. Рабочий инструмент менеджера."""
    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    date_from = (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")

    rows = con.execute("""
        SELECT cp.offer_id, cp.price, cp.min_price, cp.price_index_color,
               p.name, p.cost_price,
               COALESCE(sd.orders, 0) AS orders_30d,
               cs.total_present AS stock
        FROM current_stocks cs
        JOIN current_prices cp ON cp.offer_id = cs.offer_id
        JOIN products p ON p.offer_id = cs.offer_id
        LEFT JOIN (
            SELECT sku, SUM(orders_units) AS orders
            FROM sales_daily WHERE date >= ?
            GROUP BY sku
        ) sd ON sd.sku = p.sku
        WHERE cs.total_present > 0
          AND p.is_own = 1 AND p.is_archived = 0
          AND cp.price > 0 AND p.cost_price > 0
    """, (date_from,)).fetchall()

    items = []
    for r in rows:
        price = r["price"] or 0
        cost = r["cost_price"] or 0
        min_p = r["min_price"] or 0
        stock = r["stock"] or 0
        orders = r["orders_30d"] or 0
        color = r["price_index_color"] or "WITHOUT_INDEX"

        unit_profit = price * (1 - COMMISSION_PCT - SERVICES_PCT) - cost
        unit_margin = unit_profit / price if price else 0

        # Рекомендация менеджеру
        if color == "RED" and min_p > 0:
            target = min_p * 1.02
            new_profit = target * (1 - COMMISSION_PCT - SERVICES_PCT) - cost
            if new_profit > 0:
                recommend = f"↓ Снизить до {target:,.0f} ₽"
            else:
                recommend = "→ Снять (маржа уйдёт в минус)"
        elif color == "SUPER" and min_p > price * 0.95:
            new_target = price * 1.10
            recommend = f"↑ Поднять до {new_target:,.0f} ₽"
        elif color == "GREEN" and min_p > 0 and price < min_p * 0.9:
            new_target = price * 1.05
            recommend = f"↑ Поднять до {new_target:,.0f} ₽"
        elif unit_profit < 0:
            recommend = "❌ Убыток — поднять цену"
        elif orders == 0:
            recommend = "○ Наблюдать"
        else:
            recommend = "✓ Оставить"

        items.append({
            "offer_id": r["offer_id"],
            "name": (r["name"] or "")[:60],
            "cost": cost,
            "price": price,
            "min_price": min_p,
            "color": color,
            "unit_profit": unit_profit,
            "unit_margin": unit_margin,
            "orders_30d": orders,
            "stock": stock,
            "recommend": recommend,
        })

    # Сортировка: сначала RED (проблема), потом SUPER (можно поднять), потом остальные
    order = {"RED": 0, "YELLOW": 1, "GREEN": 2, "SUPER": 3, "WITHOUT_INDEX": 4}
    items.sort(key=lambda x: (order.get(x["color"], 9), -x["stock"]))

    from collections import Counter
    colors = Counter(i["color"] for i in items)
    total = len(items)

    data = []
    data.append(["ЦЕНЫ — только SKU с остатком (актуально из Ozon API)",
                 "", "", "", "", "", "", ""])
    data.append([f"всего SKU с остатком: {total}  |  "
                 f"🔴 RED: {colors.get('RED', 0)}  |  "
                 f"🟡 YELLOW: {colors.get('YELLOW', 0)}  |  "
                 f"🟢 GREEN: {colors.get('GREEN', 0)}  |  "
                 f"🟣 SUPER: {colors.get('SUPER', 0)}",
                 "", "", "", "", "", "", ""])
    data.append(["", "", "", "", "", "", "", ""])

    # ВЫВОДЫ
    data.append(["ВЫВОДЫ", "", "", "", "", "", "", ""])
    red_count = colors.get("RED", 0)
    super_count = colors.get("SUPER", 0)
    loss_count = sum(1 for i in items if i["unit_profit"] < 0)

    if red_count > 0:
        v1 = f"⚠ {red_count} SKU дороже рынка — снизить цену до Min"
    else:
        v1 = "✅ Нет SKU дороже рынка"

    if super_count > 0:
        v2 = f"💰 {super_count} SKU в SUPER — можно поднять цену"
    else:
        v2 = "ℹ Нет SKU в SUPER"

    if loss_count > 0:
        v3 = f"❌ {loss_count} SKU убыточны — поднять цену или снять"
    else:
        v3 = "✅ Убыточных нет"

    data.append(["", v1, "", "", "", "", "", ""])
    data.append(["", v2, "", "", "", "", "", ""])
    data.append(["", v3, "", "", "", "", "", ""])
    data.append(["", "", "", "", "", "", "", ""])

    # Таблица
    data.append(["Offer ID", "Название", "Себест", "Цена Ozon", "Min",
                 "Индекс", "Приб/ед", "Ост", "Зак", "Рекомендация"])

    for it in items:
        profit_str = f"{it['unit_profit']:+,.0f}" if it["unit_profit"] else "0"
        data.append([
            it["offer_id"],
            it["name"],
            f"{it['cost']:,.0f}",
            f"{it['price']:,.0f}",
            f"{it['min_price']:,.0f}" if it["min_price"] else "—",
            it["color"],
            profit_str,
            it["stock"],
            it["orders_30d"],
            it["recommend"],
        ])

    return data, items, 3


def format_prices(ws, items, n_verdicts=3):
    sid = ws.id
    ops = []
    ops.append({"type": "unmerge", "range": "A1:Z500"})
    ops.append({"type": "clear_notes", "range": "A1:Z500"})

    # Заголовок
    ops.append({"type": "merge", "range": "A1:J1"})
    ops.append({"type": "format", "range": "A1:J1", "format": FMT_TITLE})
    ops.append({"type": "row_height", "row": 1, "height": 40})

    sub_fmt = CellFormat(
        textFormat=TextFormat(fontSize=11, italic=True, foregroundColor=Color(0.35, 0.35, 0.35)),
        backgroundColor=SUBHEADER_BG,
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "merge", "range": "A2:J2"})
    ops.append({"type": "format", "range": "A2:J2", "format": sub_fmt})
    ops.append({"type": "row_height", "row": 2, "height": 26})

    # ВЫВОДЫ — заголовок строка 4, тезисы 5-7
    ops.append({"type": "merge", "range": "A4:J4"})
    ops.append({"type": "format", "range": "A4:J4", "format": FMT_SUBHEADER})
    ops.append({"type": "row_height", "row": 4, "height": 26})

    for i in range(n_verdicts):
        r = 5 + i
        ops.append({"type": "merge", "range": f"B{r}:J{r}"})
        ops.append({"type": "row_height", "row": r, "height": 28})

    # Таблица — строка 9
    table_start = 9
    tbl_hdr = CellFormat(
        backgroundColor=HEADER_BG,
        textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=HEADER_FG),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "format", "range": f"A{table_start}:J{table_start}", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": table_start, "height": 32})

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
        "WITHOUT_INDEX":CellFormat(textFormat=TextFormat(fontSize=10, italic=True, foregroundColor=MUTED_FG),
                                   horizontalAlignment='CENTER'),
    }
    body_center = CellFormat(textFormat=TextFormat(fontSize=10),
                             horizontalAlignment='CENTER', verticalAlignment='MIDDLE')
    body_left = CellFormat(textFormat=TextFormat(fontSize=10),
                           horizontalAlignment='LEFT', verticalAlignment='MIDDLE', wrapStrategy='CLIP')
    body_offer = CellFormat(textFormat=TextFormat(fontSize=10, bold=True),
                            horizontalAlignment='CENTER')
    body_price = CellFormat(textFormat=TextFormat(fontSize=11, bold=True),
                            horizontalAlignment='CENTER')

    r = table_start + 1
    for it in items:
        ops.append({"type": "format", "range": f"A{r}", "format": body_offer})
        ops.append({"type": "format", "range": f"B{r}", "format": body_left})
        ops.append({"type": "format", "range": f"C{r}", "format": body_center})
        ops.append({"type": "format", "range": f"D{r}", "format": body_price})
        ops.append({"type": "format", "range": f"E{r}", "format": body_center})
        ops.append({"type": "format", "range": f"F{r}", "format": color_fmt.get(it["color"], body_center)})
        if it["unit_profit"] < 0:
            pf = CellFormat(backgroundColor=BAD_BG,
                            textFormat=TextFormat(fontSize=10, bold=True, foregroundColor=BAD_FG),
                            horizontalAlignment='CENTER')
        else:
            pf = CellFormat(textFormat=TextFormat(fontSize=10, bold=True),
                            horizontalAlignment='CENTER')
        ops.append({"type": "format", "range": f"G{r}", "format": pf})
        ops.append({"type": "format", "range": f"H{r}", "format": body_center})
        ops.append({"type": "format", "range": f"I{r}", "format": body_center})
        ops.append({"type": "format", "range": f"J{r}", "format": body_left})
        ops.append({"type": "row_height", "row": r, "height": 26})
        r += 1

    # Ширины
    ops.append({"type": "width", "col": "A", "width": 130})
    ops.append({"type": "width", "col": "B", "width": 400})
    ops.append({"type": "width", "col": "C", "width": 80})
    ops.append({"type": "width", "col": "D", "width": 100})
    ops.append({"type": "width", "col": "E", "width": 90})
    ops.append({"type": "width", "col": "F", "width": 130})
    ops.append({"type": "width", "col": "G", "width": 90})
    ops.append({"type": "width", "col": "H", "width": 60})
    ops.append({"type": "width", "col": "I", "width": 60})
    ops.append({"type": "width", "col": "J", "width": 280})

    ops.append({"type": "frozen", "rows": table_start})

    last_row = table_start + len(items)
    ops.append({"type": "filter", "range": f"A{table_start}:J{last_row}"})

    n = batch_apply(ws, sid, ops)
    print(f"  Отправлено форматирований одним batch: {n}")

    # Цвет выводов
    try:
        vals = ws.get(f"B5:B{4 + n_verdicts}")
        ops2 = []
        for i, row_v in enumerate(vals):
            if not row_v:
                continue
            v = row_v[0]
            r = 5 + i
            if v.startswith("❌") or v.startswith("⚠"):
                bg, fg = BAD_BG, BAD_FG
            elif v.startswith("✅") or v.startswith("🟢"):
                bg, fg = GOOD_BG, GOOD_FG
            elif v.startswith("💰"):
                bg, fg = Color(0.95, 0.95, 0.75), Color(0.5, 0.4, 0)
            else:
                bg, fg = SUBHEADER_BG, Color(0.2, 0.2, 0.2)
            ops2.append({"type": "format", "range": f"B{r}:J{r}", "format": CellFormat(
                backgroundColor=bg,
                textFormat=TextFormat(fontSize=11, foregroundColor=fg),
                horizontalAlignment='LEFT', verticalAlignment='MIDDLE', wrapStrategy='WRAP',
            )})
        if ops2:
            batch_apply(ws, sid, ops2)
    except Exception as e:
        print(f"  [WARN] Цвет выводов: {e}")


def sync_prices(sh, con):
    print("\\n[Лист ЦЕНЫ]")
    ws = get_or_create_sheet(sh, "ЦЕНЫ")
    data, items, n_verdicts = build_prices(con)
    clear_and_write(ws, data)
    print(f"  Записано строк: {len(data)}")
    format_prices(ws, items, n_verdicts)


# ============ ЛИСТ ЗАМОРОЗКА ============
def build_frozen(con):
    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    date_from = (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")

    rows = con.execute("""
        SELECT cs.offer_id, cs.total_present AS stock,
               p.name, p.cost_price,
               COALESCE(sd.orders, 0) AS orders_30d,
               cp.price_index_color AS color
        FROM current_stocks cs
        JOIN products p ON p.offer_id = cs.offer_id
        LEFT JOIN current_prices cp ON cp.offer_id = cs.offer_id
        LEFT JOIN (
            SELECT sku, SUM(orders_units) AS orders
            FROM sales_daily WHERE date >= ? GROUP BY sku
        ) sd ON sd.sku = p.sku
        WHERE cs.total_present > 0
          AND p.is_own = 1 AND p.is_archived = 0
          AND p.cost_price > 0
    """, (date_from,)).fetchall()

    items = []
    for r in rows:
        stock = r["stock"] or 0
        cost = r["cost_price"] or 0
        frozen = stock * cost
        orders = r["orders_30d"] or 0
        days = stock / (orders / 30) if orders > 0 else 999
        items.append({
            "offer_id": r["offer_id"],
            "name": (r["name"] or "")[:55],
            "stock": int(stock),
            "cost": cost,
            "frozen": frozen,
            "orders_30d": orders,
            "days_to_sell": days,
            "color": r["color"] or "",
        })
    items.sort(key=lambda x: -x["frozen"])

    total_frozen = sum(i["frozen"] for i in items)
    dead = [i for i in items if i["orders_30d"] == 0]
    dead_money = sum(i["frozen"] for i in dead)

    data = [
        ["ЗАМОРОЗКА В СКЛАДЕ", "", "", "", "", "", "", ""],
        [f"актуально из Ozon API на {datetime.now().strftime('%d.%m %H:%M')}", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", ""],
        ["ИТОГИ", "", "", "", "", "", "", ""],
        ["SKU с остатком", len(items), "", "", "", "", "", ""],
        ["Всего заморожено", f"{total_frozen:,.0f} ₽", "", "", "", "", "", ""],
        ["Мёртвые (0 продаж 30д)", f"{len(dead)} SKU = {dead_money:,.0f} ₽",
         f"({dead_money / total_frozen * 100:.0f}%)" if total_frozen else "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", ""],
        ["ТОП-30 ПО ЗАМОРОЗКЕ", "", "", "", "", "", "", ""],
        ["#", "Offer ID", "Название", "Ост", "Себест", "Замор", "Дней", "Индекс"],
    ]
    for i, it in enumerate(items[:30], 1):
        days_str = f"{it['days_to_sell']:.0f}" if it['days_to_sell'] < 999 else "∞"
        data.append([i, it["offer_id"], it["name"], it["stock"],
                     f"{it['cost']:,.0f}", f"{it['frozen']:,.0f}",
                     days_str, it["color"]])
    return data, items


def format_frozen(ws, items):
    sid = ws.id
    ops = []
    ops.append({"type": "unmerge", "range": "A1:Z100"})
    ops.append({"type": "clear_notes", "range": "A1:Z100"})

    ops.append({"type": "merge", "range": "A1:H1"})
    ops.append({"type": "format", "range": "A1:H1", "format": FMT_TITLE})
    ops.append({"type": "row_height", "row": 1, "height": 40})

    sub_fmt = CellFormat(
        textFormat=TextFormat(fontSize=11, italic=True, foregroundColor=Color(0.35, 0.35, 0.35)),
        backgroundColor=SUBHEADER_BG, horizontalAlignment='CENTER', verticalAlignment='MIDDLE')
    ops.append({"type": "merge", "range": "A2:H2"})
    ops.append({"type": "format", "range": "A2:H2", "format": sub_fmt})
    ops.append({"type": "row_height", "row": 2, "height": 26})

    ops.append({"type": "merge", "range": "A4:H4"})
    ops.append({"type": "format", "range": "A4:H4", "format": FMT_SUBHEADER})
    ops.append({"type": "row_height", "row": 4, "height": 26})

    label_fmt = CellFormat(textFormat=TextFormat(bold=True, fontSize=11),
                           horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
                           backgroundColor=SUBHEADER_BG)
    big_num = CellFormat(textFormat=TextFormat(bold=True, fontSize=14,
                                                foregroundColor=Color(0.1, 0.3, 0.6)),
                         horizontalAlignment='CENTER', verticalAlignment='MIDDLE')
    for r in range(5, 8):
        ops.append({"type": "row_height", "row": r, "height": 28})
        ops.append({"type": "format", "range": f"A{r}", "format": label_fmt})
        ops.append({"type": "format", "range": f"B{r}", "format": big_num})

    ops.append({"type": "merge", "range": "A9:H9"})
    ops.append({"type": "format", "range": "A9:H9", "format": FMT_SUBHEADER})
    ops.append({"type": "row_height", "row": 9, "height": 26})

    tbl_hdr = CellFormat(backgroundColor=HEADER_BG,
                         textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=HEADER_FG),
                         horizontalAlignment='CENTER', verticalAlignment='MIDDLE')
    ops.append({"type": "format", "range": "A10:H10", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 10, "height": 32})

    body_center = CellFormat(textFormat=TextFormat(fontSize=10),
                             horizontalAlignment='CENTER', verticalAlignment='MIDDLE')
    body_left = CellFormat(textFormat=TextFormat(fontSize=10),
                           horizontalAlignment='LEFT', verticalAlignment='MIDDLE', wrapStrategy='CLIP')
    body_offer = CellFormat(textFormat=TextFormat(fontSize=10, bold=True),
                            horizontalAlignment='CENTER')
    body_money = CellFormat(textFormat=TextFormat(fontSize=10, bold=True),
                            horizontalAlignment='CENTER')

    for r in range(11, 41):
        ops.append({"type": "format", "range": f"A{r}", "format": body_center})
        ops.append({"type": "format", "range": f"B{r}", "format": body_offer})
        ops.append({"type": "format", "range": f"C{r}", "format": body_left})
        ops.append({"type": "format", "range": f"D{r}", "format": body_center})
        ops.append({"type": "format", "range": f"E{r}", "format": body_center})
        ops.append({"type": "format", "range": f"F{r}", "format": body_money})
        ops.append({"type": "format", "range": f"G{r}", "format": body_center})
        ops.append({"type": "format", "range": f"H{r}", "format": body_center})
        ops.append({"type": "row_height", "row": r, "height": 26})

    for c, w in [("A", 40), ("B", 140), ("C", 400), ("D", 60), ("E", 90),
                 ("F", 110), ("G", 70), ("H", 130)]:
        ops.append({"type": "width", "col": c, "width": w})

    ops.append({"type": "frozen", "rows": 10})

    n = batch_apply(ws, sid, ops)
    print(f"  Отправлено форматирований одним batch: {n}")

    try:
        vals = ws.get("H11:H40")
        color_fmt = {
            "RED":   CellFormat(backgroundColor=BAD_BG,
                                textFormat=TextFormat(bold=True, foregroundColor=BAD_FG),
                                horizontalAlignment='CENTER'),
            "SUPER": CellFormat(backgroundColor=Color(0.85, 0.95, 0.85),
                                textFormat=TextFormat(bold=True, foregroundColor=Color(0.1, 0.45, 0.1)),
                                horizontalAlignment='CENTER'),
            "GREEN": CellFormat(backgroundColor=GOOD_BG,
                                textFormat=TextFormat(bold=True, foregroundColor=GOOD_FG),
                                horizontalAlignment='CENTER'),
        }
        ops2 = []
        for i, row in enumerate(vals):
            c = (row[0] or "").strip() if row else ""
            if c in color_fmt:
                ops2.append({"type": "format", "range": f"H{11+i}", "format": color_fmt[c]})
        if ops2:
            batch_apply(ws, sid, ops2)
            print(f"  Цвет индексов: {len(ops2)}")
    except Exception as e:
        print(f"  [WARN] Цвет: {e}")


def sync_frozen(sh, con):
    print("\\n[Лист ЗАМОРОЗКА]")
    ws = get_or_create_sheet(sh, "ЗАМОРОЗКА")
    data, items = build_frozen(con)
    clear_and_write(ws, data)
    print(f"  Записано строк: {len(data)}")
    format_frozen(ws, items)


# ============ ЛИСТ ДЕНЬГИ (упрощённый) ============
def build_money(con):
    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    periods = [
        ("7 дней", (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d"), max_date),
        ("30 дней", (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d"), max_date),
        ("с 1 августа", "2026-08-01", max_date),
    ]

    def calc(d1, d2):
        rows = con.execute("""
            SELECT p.sku, p.cost_price,
                   SUM(sd.revenue) AS rev, SUM(sd.orders_units) AS orders
            FROM sales_daily sd
            JOIN products p ON p.sku = sd.sku
            WHERE sd.date BETWEEN ? AND ?
              AND p.is_own = 1 AND p.is_archived = 0
            GROUP BY p.sku
        """, (d1, d2)).fetchall()
        rev = cost = comm = serv = profit = 0.0
        orders = 0
        for sku, cp, r, o in rows:
            r = r or 0; o = o or 0; cp = cp or 0
            c = cp * o
            cm = r * COMMISSION_PCT
            sv = r * SERVICES_PCT
            pb = r - c - cm - sv
            tx = pb * TAX_PCT if pb > 0 else 0
            rev += r; cost += c; comm += cm; serv += sv
            profit += pb - tx; orders += o
        m = profit / rev if rev else 0
        avg = rev / orders if orders else 0
        return rev, cost, comm, serv, profit, m, orders, avg

    data = [
        ["ДЕНЬГИ", "", "", "", "", "", "", ""],
        [f"ставки: комиссия {COMMISSION_PCT*100:.2f}%, услуги {SERVICES_PCT*100:.1f}%", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", ""],
        ["Период", "Выручка", "Себест", "Комиссия", "Услуги", "Прибыль", "Маржа", "Заказов"],
    ]
    for label, d1, d2 in periods:
        rev, cost, comm, serv, profit, m, orders, avg = calc(d1, d2)
        data.append([label, f"{rev:,.0f}", f"{cost:,.0f}", f"{comm:,.0f}",
                     f"{serv:,.0f}", f"{profit:,.0f}", f"{m*100:.1f}%", orders])

    data.append(["", "", "", "", "", "", "", ""])
    data.append(["ПО МЕСЯЦАМ", "", "", "", "", "", "", ""])
    data.append(["Месяц", "Выручка", "Себест", "Комиссия", "Услуги", "Прибыль", "Маржа", "Заказов"])

    months = con.execute("""
        SELECT substr(date, 1, 7) AS m, MIN(date), MAX(date)
        FROM sales_daily GROUP BY m ORDER BY m DESC
    """).fetchall()
    for m, d1, d2 in months:
        rev, cost, comm, serv, profit, mrg, orders, avg = calc(d1, d2)
        label = {"2026-06":"Июнь","2026-07":"Июль","2026-08":"Август","2026-09":"Сентябрь"}.get(m, m)
        data.append([f"{label} 2026", f"{rev:,.0f}", f"{cost:,.0f}", f"{comm:,.0f}",
                     f"{serv:,.0f}", f"{profit:,.0f}", f"{mrg*100:.1f}%", orders])
    return data


def format_money(ws):
    sid = ws.id
    ops = []
    ops.append({"type": "unmerge", "range": "A1:Z50"})
    ops.append({"type": "clear_notes", "range": "A1:Z50"})

    ops.append({"type": "merge", "range": "A1:H1"})
    ops.append({"type": "format", "range": "A1:H1", "format": FMT_TITLE})
    ops.append({"type": "row_height", "row": 1, "height": 40})

    sub_fmt = CellFormat(textFormat=TextFormat(fontSize=11, italic=True, foregroundColor=Color(0.35, 0.35, 0.35)),
                         backgroundColor=SUBHEADER_BG, horizontalAlignment='CENTER', verticalAlignment='MIDDLE')
    ops.append({"type": "merge", "range": "A2:H2"})
    ops.append({"type": "format", "range": "A2:H2", "format": sub_fmt})
    ops.append({"type": "row_height", "row": 2, "height": 26})

    tbl_hdr = CellFormat(backgroundColor=HEADER_BG,
                         textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=HEADER_FG),
                         horizontalAlignment='CENTER', verticalAlignment='MIDDLE')

    ops.append({"type": "format", "range": "A4:H4", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 4, "height": 36})
    for r in range(5, 8):
        ops.append({"type": "row_height", "row": r, "height": 32})

    ops.append({"type": "merge", "range": "A9:H9"})
    ops.append({"type": "format", "range": "A9:H9", "format": FMT_SUBHEADER})
    ops.append({"type": "row_height", "row": 9, "height": 26})

    ops.append({"type": "format", "range": "A10:H10", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 10, "height": 36})
    for r in range(11, 15):
        ops.append({"type": "row_height", "row": r, "height": 32})

    for c, w in [("A", 140), ("B", 130), ("C", 130), ("D", 120), ("E", 130),
                 ("F", 130), ("G", 100), ("H", 100)]:
        ops.append({"type": "width", "col": c, "width": w})

    ops.append({"type": "frozen", "rows": 4})

    n = batch_apply(ws, sid, ops)
    print(f"  Отправлено форматирований одним batch: {n}")

    # Цвет маржи
    try:
        vals = ws.get("G5:G15")
        ops2 = []
        for i, row in enumerate(vals):
            if not row:
                continue
            v = row[0].strip().rstrip("%")
            try:
                m = float(v)
            except ValueError:
                continue
            r = 5 + i
            if r in (8, 9, 10, 11):
                continue
            if m < 5:
                bg, fg = BAD_BG, BAD_FG
            elif m < 15:
                bg, fg = WARN_BG, Color(0.5, 0.4, 0)
            else:
                bg, fg = GOOD_BG, GOOD_FG
            ops2.append({"type": "format", "range": f"G{r}", "format": CellFormat(
                backgroundColor=bg,
                textFormat=TextFormat(fontSize=12, bold=True, foregroundColor=fg),
                horizontalAlignment='CENTER', verticalAlignment='MIDDLE')})
        if ops2:
            batch_apply(ws, sid, ops2)
    except Exception:
        pass


def sync_money(sh, con):
    print("\\n[Лист ДЕНЬГИ]")
    ws = get_or_create_sheet(sh, "ДЕНЬГИ")
    data = build_money(con)
    clear_and_write(ws, data)
    print(f"  Записано строк: {len(data)}")
    format_money(ws)


# ============ ЛИСТ РЕЗУЛЬТАТ (упрощённый) ============
def build_result(con):
    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    min_date = "2026-08-01"
    rows = con.execute("""
        SELECT p.sku, p.cost_price,
               SUM(sd.revenue) AS rev, SUM(sd.orders_units) AS orders
        FROM sales_daily sd
        JOIN products p ON p.sku = sd.sku
        WHERE sd.date BETWEEN ? AND ?
          AND p.is_own = 1 AND p.is_archived = 0
        GROUP BY p.sku
    """, (min_date, max_date)).fetchall()

    rev = cost = profit = 0.0
    orders = 0
    for sku, cp, r, o in rows:
        r = r or 0; o = o or 0; cp = cp or 0
        c = cp * o
        cm = r * COMMISSION_PCT
        sv = r * SERVICES_PCT
        pb = r - c - cm - sv
        tx = pb * TAX_PCT if pb > 0 else 0
        rev += r; cost += c; profit += pb - tx; orders += o
    margin = profit / rev if rev else 0
    avg = rev / orders if orders else 0

    con.execute("""
        CREATE TABLE IF NOT EXISTS dashboard_snapshots (
            run_at TEXT PRIMARY KEY, period_from TEXT, period_to TEXT,
            revenue REAL, profit REAL, margin REAL, orders INTEGER, avg_check REAL)
    """)
    con.commit()
    prev = con.execute("""
        SELECT run_at, revenue, profit, margin, orders, avg_check
        FROM dashboard_snapshots ORDER BY run_at DESC LIMIT 1
    """).fetchone()

    def delta(c, o):
        if not o:
            return "—"
        return f"{(c - o) / abs(o) * 100:+.1f}%"

    data = [
        ["РЕЗУЛЬТАТ", "", "", ""],
        [f"период с 1 августа по {max_date}", "", "", ""],
        ["", "", "", ""],
        ["Показатель", "Сейчас", "Прошлый запуск", "Δ"],
    ]
    if prev:
        p_run, p_rev, p_profit, p_margin, p_orders, p_avg = prev
        data.append(["Выручка", f"{rev:,.0f}", f"{p_rev:,.0f}", delta(rev, p_rev)])
        data.append(["Прибыль", f"{profit:,.0f}", f"{p_profit:,.0f}", delta(profit, p_profit)])
        data.append(["Маржа", f"{margin*100:.1f}%", f"{p_margin*100:.1f}%", ""])
        data.append(["Заказы", orders, p_orders, delta(orders, p_orders)])
        data.append(["Ср. чек", f"{avg:,.0f}", f"{p_avg:,.0f}", delta(avg, p_avg)])
    else:
        data.append(["Выручка", f"{rev:,.0f}", "—", "первый запуск"])
        data.append(["Прибыль", f"{profit:,.0f}", "—", ""])
        data.append(["Маржа", f"{margin*100:.1f}%", "—", ""])
        data.append(["Заказы", orders, "—", ""])
        data.append(["Ср. чек", f"{avg:,.0f}", "—", ""])

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    con.execute("""
        INSERT OR REPLACE INTO dashboard_snapshots
        (run_at, period_from, period_to, revenue, profit, margin, orders, avg_check)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (now, min_date, max_date, rev, profit, margin, orders, avg))
    con.commit()
    return data


def format_result(ws):
    sid = ws.id
    ops = []
    ops.append({"type": "unmerge", "range": "A1:Z50"})
    ops.append({"type": "clear_notes", "range": "A1:Z50"})

    ops.append({"type": "merge", "range": "A1:D1"})
    ops.append({"type": "format", "range": "A1:D1", "format": FMT_TITLE})
    ops.append({"type": "row_height", "row": 1, "height": 40})

    sub_fmt = CellFormat(textFormat=TextFormat(fontSize=11, italic=True, foregroundColor=Color(0.35, 0.35, 0.35)),
                         backgroundColor=SUBHEADER_BG, horizontalAlignment='CENTER', verticalAlignment='MIDDLE')
    ops.append({"type": "merge", "range": "A2:D2"})
    ops.append({"type": "format", "range": "A2:D2", "format": sub_fmt})
    ops.append({"type": "row_height", "row": 2, "height": 26})

    tbl_hdr = CellFormat(backgroundColor=HEADER_BG,
                         textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=HEADER_FG),
                         horizontalAlignment='CENTER', verticalAlignment='MIDDLE')
    ops.append({"type": "format", "range": "A4:D4", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 4, "height": 36})
    for r in range(5, 10):
        ops.append({"type": "row_height", "row": r, "height": 32})

    for c, w in [("A", 160), ("B", 150), ("C", 150), ("D", 120)]:
        ops.append({"type": "width", "col": c, "width": w})

    ops.append({"type": "frozen", "rows": 4})

    n = batch_apply(ws, sid, ops)
    print(f"  Отправлено форматирований одним batch: {n}")

    # Δ-цвета
    try:
        vals = ws.get("D5:D9")
        ops2 = []
        for i, row in enumerate(vals):
            if not row:
                continue
            v = row[0].strip()
            r = 5 + i
            if v.startswith("+") and any(c.isdigit() for c in v):
                ops2.append({"type": "format", "range": f"D{r}", "format": CellFormat(
                    backgroundColor=GOOD_BG,
                    textFormat=TextFormat(fontSize=11, bold=True, foregroundColor=GOOD_FG),
                    horizontalAlignment='CENTER')})
            elif v.startswith("-") and any(c.isdigit() for c in v):
                ops2.append({"type": "format", "range": f"D{r}", "format": CellFormat(
                    backgroundColor=BAD_BG,
                    textFormat=TextFormat(fontSize=11, bold=True, foregroundColor=BAD_FG),
                    horizontalAlignment='CENTER')})
        if ops2:
            batch_apply(ws, sid, ops2)
    except Exception:
        pass


def sync_result(sh, con):
    print("\\n[Лист РЕЗУЛЬТАТ]")
    ws = get_or_create_sheet(sh, "РЕЗУЛЬТАТ")
    data = build_result(con)
    clear_and_write(ws, data)
    print(f"  Записано строк: {len(data)}")
    format_result(ws)


'''

src, n = pattern.subn(new_block, src)
print(f"[{'OK' if n else 'FAIL'}] build_prices/format_prices/sync_prices + frozen + money + result восстановлены")

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("\nГотово. Запускай: py sheets_sync.py")
