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
            r = r or 0
            o = o or 0
            cp = cp or 0
            c = cp * o
            cm = r * COMMISSION_PCT
            sv = r * SERVICES_PCT
            pb = r - c - cm - sv
            tx = pb * TAX_PCT if pb > 0 else 0
            rev += r
            cost += c
            comm += cm
            serv += sv
            profit += pb - tx
            orders += o
        m = profit / rev if rev else 0
        avg = rev / orders if orders else 0
        return rev, cost, comm, serv, profit, m, orders, avg

    def verdict(m):
        if m < 0.05:
            return "Убыток"
        if m < 0.10:
            return "Тонко"
        if m < 0.15:
            return "Норма"
        return "Отлично"

    period_stats = {}
    data = [
        ["ДЕНЬГИ", "", "", "", "", "", "", "", "", ""],
        ["ставки: комиссия " + str(round(COMMISSION_PCT*100, 2)) + "%, услуги " + str(round(SERVICES_PCT*100, 1)) + "%", "", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
        ["Период", "Выручка", "Себестоимость", "Комиссия", "Услуги Ozon", "Прибыль", "Маржа", "Заказов", "Ср. чек", "Оценка"],
    ]
    for label, d1, d2 in periods:
        rev, cost, comm, serv, profit, m, orders, avg = calc(d1, d2)
        period_stats[label] = (rev, cost, comm, serv, profit, m, orders, avg)
        data.append([label, f"{rev:,.0f}", f"{cost:,.0f}", f"{comm:,.0f}",
                     f"{serv:,.0f}", f"{profit:,.0f}", f"{m*100:.1f}%", orders,
                     f"{avg:,.0f}", verdict(m)])

    data.append(["", "", "", "", "", "", "", "", "", ""])

    # ПО МЕСЯЦАМ
    data.append(["ПО МЕСЯЦАМ", "", "", "", "", "", "", "", "", ""])
    data.append(["Месяц", "Выручка", "Себестоимость", "Комиссия", "Услуги Ozon", "Прибыль", "Маржа", "Заказов", "Ср. чек", "Оценка"])

    months = con.execute("""
        SELECT substr(date, 1, 7) AS m, MIN(date), MAX(date)
        FROM sales_daily GROUP BY m ORDER BY m DESC
    """).fetchall()
    month_stats = {}
    for m, d1, d2 in months:
        rev, cost, comm, serv, profit, mrg, orders, avg = calc(d1, d2)
        month_stats[m] = (rev, cost, comm, serv, profit, mrg, orders, avg)
        label = {"2026-06": "Июнь 2026", "2026-07": "Июль 2026", "2026-08": "Август 2026", "2026-09": "Сентябрь 2026"}.get(m, m)
        data.append([label, f"{rev:,.0f}", f"{cost:,.0f}", f"{comm:,.0f}",
                     f"{serv:,.0f}", f"{profit:,.0f}", f"{mrg*100:.1f}%", orders,
                     f"{avg:,.0f}", verdict(mrg)])

    data.append(["", "", "", "", "", "", "", "", "", ""])

    # ВЫВОДЫ
    data.append(["ВЫВОДЫ", "", "", "", "", "", "", "", "", ""])

    s30 = period_stats["30 дней"]
    margin_30 = s30[5]
    cost_pct = s30[1] / s30[0] if s30[0] else 0
    serv_pct = s30[4] / s30[0] if s30[0] else 0

    if margin_30 < 0.05:
        v1 = "Критично: маржа " + f"{margin_30*100:.1f}%" + " — работаем почти в ноль"
    elif margin_30 < 0.10:
        v1 = "Тонко: маржа " + f"{margin_30*100:.1f}%" + " — любой сбой уводит в минус"
    elif margin_30 < 0.15:
        v1 = "Норма: маржа " + f"{margin_30*100:.1f}%" + " — есть куда расти"
    else:
        v1 = "Отлично: маржа " + f"{margin_30*100:.1f}%"

    aug = month_stats.get("2026-08")
    sep = month_stats.get("2026-09")
    if aug and sep:
        d_m = (sep[5] - aug[5]) * 100
        if d_m < -1:
            v2 = "Падение маржи: сентябрь " + f"{sep[5]*100:.1f}%" + " vs август " + f"{aug[5]*100:.1f}%" + " (" + f"{d_m:+.1f}" + " п.п.) — разобраться с убыточными SKU"
        elif d_m > 1:
            v2 = "Рост маржи: " + f"{aug[5]*100:.1f}%" + " -> " + f"{sep[5]*100:.1f}%" + " (" + f"{d_m:+.1f}" + " п.п.)"
        else:
            v2 = "Маржа стабильна: " + f"{sep[5]*100:.1f}%"
    else:
        v2 = "Динамика: недостаточно данных"

    if cost_pct > 0.75:
        v3 = "Себестоимость съедает " + f"{cost_pct*100:.0f}%" + " выручки — главный рычаг роста"
    elif cost_pct > 0.65:
        v3 = "Себестоимость " + f"{cost_pct*100:.0f}%" + " — торговаться с поставщиком"
    else:
        v3 = "Себестоимость " + f"{cost_pct*100:.0f}%" + " — приемлемо"

    if serv_pct > 0.15:
        v4 = "Услуги Ozon " + f"{serv_pct*100:.1f}%" + " — проверить логистику и возвраты"
    else:
        v4 = "Услуги Ozon " + f"{serv_pct*100:.1f}%" + " — в норме"

    from plan_core import get_actions
    month_ago = (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")
    actions = get_actions(con, month_ago, max_date)
    if actions:
        top = actions[0]
        total_effect = sum(a["effect"] for a in actions)
        v5 = "Действия: " + top["offer_id"] + " (" + top["category"] + ", " + f"{top['effect']:,.0f}" + " руб), всего " + str(len(actions)) + " SKU, потенциал " + f"{total_effect:,.0f}" + " руб/мес"
    else:
        v5 = "Действий нет"

    data.append(["", v1, "", "", "", "", "", "", "", ""])
    data.append(["", v2, "", "", "", "", "", "", "", ""])
    data.append(["", v3, "", "", "", "", "", "", "", ""])
    data.append(["", v4, "", "", "", "", "", "", "", ""])
    data.append(["", v5, "", "", "", "", "", "", "", ""])

    data.append(["", "", "", "", "", "", "", "", "", ""])
    data.append(["PremiumSubscription " + f"{PREMIUM_FIXED:,.0f}" + " руб/мес — постоянный расход, не в марже", "", "", "", "", "", "", "", "", ""])

    return data


def format_money(ws):
    sid = ws.id
    ops = []
    ops.append({"type": "unmerge", "range": "A1:Z50"})
    ops.append({"type": "clear_notes", "range": "A1:Z50"})

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

    tbl_hdr = CellFormat(
        backgroundColor=HEADER_BG,
        textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=HEADER_FG),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "format", "range": "A4:J4", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 4, "height": 36})

    body_label = CellFormat(
        textFormat=TextFormat(fontSize=11, bold=True),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
        backgroundColor=SUBHEADER_BG,
    )
    body_money = CellFormat(
        textFormat=TextFormat(fontSize=11),
        horizontalAlignment='RIGHT', verticalAlignment='MIDDLE',
    )
    body_margin = CellFormat(
        textFormat=TextFormat(fontSize=12, bold=True),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    body_center = CellFormat(
        textFormat=TextFormat(fontSize=11),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "format", "range": "A4:J4", "format": tbl_hdr})
    for r in range(5, 8):
        ops.append({"type": "format", "range": f"A{r}", "format": body_label})
        ops.append({"type": "format", "range": f"B{r}:F{r}", "format": body_money})
        ops.append({"type": "format", "range": f"G{r}", "format": body_margin})
        ops.append({"type": "format", "range": f"H{r}:J{r}", "format": body_center})
        ops.append({"type": "row_height", "row": r, "height": 32})

    # Легенда (строка 8)
    legend_fmt = CellFormat(
        textFormat=TextFormat(fontSize=9, italic=True, foregroundColor=MUTED_FG),
        backgroundColor=Color(0.98, 0.98, 0.98),
        horizontalAlignment='LEFT', verticalAlignment='MIDDLE', wrapStrategy='WRAP',
    )
    ops.append({"type": "merge", "range": "A8:J8"})
    ops.append({"type": "format", "range": "A8:J8", "format": legend_fmt})
    ops.append({"type": "row_height", "row": 8, "height": 30})

    # ПО МЕСЯЦАМ — 10
    ops.append({"type": "merge", "range": "A10:J10"})
    ops.append({"type": "format", "range": "A10:J10", "format": FMT_SUBHEADER})
    ops.append({"type": "row_height", "row": 10, "height": 28})

    ops.append({"type": "format", "range": "A11:J11", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 11, "height": 36})

    for r in range(12, 16):
        ops.append({"type": "format", "range": f"A{r}", "format": body_label})
        ops.append({"type": "format", "range": f"B{r}:F{r}", "format": body_money})
        ops.append({"type": "format", "range": f"G{r}", "format": body_margin})
        ops.append({"type": "format", "range": f"H{r}:J{r}", "format": body_center})
        ops.append({"type": "row_height", "row": r, "height": 32})

    # ВЫВОДЫ — 17
    ops.append({"type": "merge", "range": "A17:J17"})
    ops.append({"type": "format", "range": "A17:J17", "format": FMT_SUBHEADER})
    ops.append({"type": "row_height", "row": 17, "height": 28})

    for r in range(18, 23):
        ops.append({"type": "merge", "range": f"B{r}:J{r}"})
        ops.append({"type": "row_height", "row": r, "height": 30})

    # Premium — 24
    premium_fmt = CellFormat(
        backgroundColor=SUBHEADER_BG,
        textFormat=TextFormat(fontSize=11, italic=True, foregroundColor=MUTED_FG),
        horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "merge", "range": "A24:J24"})
    ops.append({"type": "format", "range": "A24:J24", "format": premium_fmt})
    ops.append({"type": "row_height", "row": 24, "height": 26})

    ops.append({"type": "width", "col": "A", "width": 140})
    ops.append({"type": "width", "col": "B", "width": 130})
    ops.append({"type": "width", "col": "C", "width": 130})
    ops.append({"type": "width", "col": "D", "width": 120})
    ops.append({"type": "width", "col": "E", "width": 130})
    ops.append({"type": "width", "col": "F", "width": 130})
    ops.append({"type": "width", "col": "G", "width": 100})
    ops.append({"type": "width", "col": "H", "width": 100})
    ops.append({"type": "width", "col": "I", "width": 120})
    ops.append({"type": "width", "col": "J", "width": 130})

    ops.append({"type": "frozen", "rows": 4})

    n = batch_apply(ws, sid, ops)
    print("  Форматирование: " + str(n))

    # Цвет маржи G5:G15
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
                bg, fg = WARN_BG, Color(0.5, 0.4, 0.0)
            else:
                bg, fg = GOOD_BG, GOOD_FG
            ops2.append({"type": "format", "range": f"G{r}", "format": CellFormat(
                backgroundColor=bg,
                textFormat=TextFormat(fontSize=12, bold=True, foregroundColor=fg),
                horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
            )})
        if ops2:
            batch_apply(ws, sid, ops2)
            print("  Цвет маржи: " + str(len(ops2)))
    except Exception as e:
        print("  WARN: " + str(e))

    # Цвет выводов 18-22
    try:
        vals = ws.get("B18:B22")
        ops3 = []
        for i, row in enumerate(vals):
            if not row:
                continue
            v = row[0]
            r = 18 + i
            if v.startswith("Критично") or v.startswith("Тонко") or v.startswith("Падение") or v.startswith("Себестоимость съедает"):
                bg, fg = BAD_BG, BAD_FG
            elif v.startswith("Норма") or v.startswith("Отлично") or v.startswith("Рост") or v.startswith("Услуги Ozon"):
                bg, fg = GOOD_BG, GOOD_FG
            elif v.startswith("Действия"):
                bg, fg = Color(0.90, 0.94, 1.0), Color(0.10, 0.20, 0.50)
            elif v.startswith("Себестоимость"):
                bg, fg = WARN_BG, Color(0.5, 0.4, 0.0)
            else:
                bg, fg = SUBHEADER_BG, Color(0.2, 0.2, 0.2)
            ops3.append({"type": "format", "range": f"B{r}:J{r}", "format": CellFormat(
                backgroundColor=bg,
                textFormat=TextFormat(fontSize=11, foregroundColor=fg),
                horizontalAlignment='LEFT', verticalAlignment='MIDDLE', wrapStrategy='WRAP',
            )})
        if ops3:
            batch_apply(ws, sid, ops3)
            print("  Цвет выводов: " + str(len(ops3)))
    except Exception as e:
        print("  WARN: " + str(e))


def sync_money(sh, con):
    print()
    print("[Лист ДЕНЬГИ]")
    ws = get_or_create_sheet(sh, "ДЕНЬГИ")
    data = build_money(con)
    clear_and_write(ws, data)
    print("  Записано строк: " + str(len(data)))
    format_money(ws)


