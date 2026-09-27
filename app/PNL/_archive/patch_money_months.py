"""
patch_money_months.py — разбивка по месяцам + замена «весь период» на «с августа».
"""
import re

src = open("sheets_sync.py", encoding="utf-8").read()

# ============ НОВЫЙ build_money ============
new_build_money = '''def build_money(con):
    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    periods = [
        ("7 дней", (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d"), max_date),
        ("30 дней", (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d"), max_date),
        ("с 1 августа", "2026-08-01", max_date),
    ]

    data = [
        ["ДЕНЬГИ", "", "", "", "", "", "", "", ""],
        [f"ставки: комиссия {COMMISSION_PCT*100:.2f}%, услуги {SERVICES_PCT*100:.1f}%",
         "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", ""],
        ["Период", "Выручка", "Себестоимость", "Комиссия", "Услуги Ozon",
         "Прибыль", "Маржа", "Заказов", "Ср. чек"],
    ]

    # Считаем функцию для периода
    def calc_period(d1, d2):
        rows = con.execute("""
            SELECT p.sku, p.cost_price,
                   SUM(sd.revenue) AS revenue,
                   SUM(sd.orders_units) AS orders
            FROM sales_daily sd
            JOIN products p ON p.sku = sd.sku
            WHERE sd.date BETWEEN ? AND ?
              AND p.is_own = 1 AND p.is_archived = 0
            GROUP BY p.sku
        """, (d1, d2)).fetchall()

        rev = cost = comm = serv = profit = 0.0
        orders = 0
        for sku, cost_price, r, o in rows:
            r = r or 0
            o = o or 0
            cost_price = cost_price or 0
            c = cost_price * o
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
        margin = profit / rev if rev else 0
        avg = rev / orders if orders else 0
        return rev, cost, comm, serv, profit, margin, orders, avg

    for label, d1, d2 in periods:
        rev, cost, comm, serv, profit, margin, orders, avg = calc_period(d1, d2)
        data.append([
            label,
            f"{rev:,.0f}", f"{cost:,.0f}", f"{comm:,.0f}", f"{serv:,.0f}",
            f"{profit:,.0f}", f"{margin*100:.1f}%", orders, f"{avg:,.0f}",
        ])

    # Разбивка по месяцам
    data.append(["", "", "", "", "", "", "", "", ""])
    data.append(["ПО МЕСЯЦАМ", "", "", "", "", "", "", "", ""])
    data.append(["Месяц", "Выручка", "Себестоимость", "Комиссия", "Услуги Ozon",
                 "Прибыль", "Маржа", "Заказов", "Ср. чек"])

    months = con.execute("""
        SELECT substr(date, 1, 7) AS m, MIN(date), MAX(date)
        FROM sales_daily GROUP BY m ORDER BY m DESC
    """).fetchall()

    for m, d1, d2 in months:
        rev, cost, comm, serv, profit, margin, orders, avg = calc_period(d1, d2)
        label = {
            "2026-06": "Июнь 2026",
            "2026-07": "Июль 2026",
            "2026-08": "Август 2026",
            "2026-09": "Сентябрь 2026",
        }.get(m, m)
        data.append([
            label,
            f"{rev:,.0f}", f"{cost:,.0f}", f"{comm:,.0f}", f"{serv:,.0f}",
            f"{profit:,.0f}", f"{margin*100:.1f}%", orders, f"{avg:,.0f}",
        ])

    data.append(["", "", "", "", "", "", "", "", ""])
    data.append([f"PremiumSubscription {PREMIUM_FIXED:,.0f} ₽/мес — постоянный расход, не в марже",
                 "", "", "", "", "", "", "", ""])
    return data
'''

pattern = re.compile(r"def build_money\(con\):.*?(?=\ndef build_result)", re.DOTALL)
src, n = pattern.subn(new_build_money + "\n\n", src)
print(f"[{'OK' if n else 'FAIL'}] build_money переписан — с разбивкой по месяцам")

# ============ ОБНОВЛЯЕМ format_money под новую структуру ============
# Строки: 1 заголовок, 2 подзаголовок, 3 пусто, 4 заголовки, 5-7 периоды,
# 8 пусто, 9 ПО МЕСЯЦАМ, 10 заголовки, 11-14 месяцы, 15 пусто, 16 Premium

new_format_money = '''def format_money(ws):
    sid = ws.id
    ops = []

    ops.append({"type": "unmerge", "range": "A1:Z50"})
    ops.append({"type": "clear_notes", "range": "A1:Z50"})

    # Заголовок
    ops.append({"type": "merge", "range": "A1:I1"})
    ops.append({"type": "format", "range": "A1:I1", "format": FMT_TITLE})
    ops.append({"type": "row_height", "row": 1, "height": 40})

    # Подзаголовок
    sub_fmt = CellFormat(
        textFormat=TextFormat(fontSize=11, italic=True, foregroundColor=Color(0.35, 0.35, 0.35)),
        backgroundColor=SUBHEADER_BG,
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "merge", "range": "A2:I2"})
    ops.append({"type": "format", "range": "A2:I2", "format": sub_fmt})
    ops.append({"type": "row_height", "row": 2, "height": 26})

    # Заголовки таблицы 1 (строка 4)
    tbl_hdr = CellFormat(
        backgroundColor=HEADER_BG,
        textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=HEADER_FG),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "format", "range": "A4:I4", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 4, "height": 36})

    # Данные периодов 5-7
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

    for r in range(5, 8):
        ops.append({"type": "format", "range": f"A{r}", "format": body_label})
        ops.append({"type": "format", "range": f"B{r}:F{r}", "format": body_money})
        ops.append({"type": "format", "range": f"G{r}", "format": body_margin})
        ops.append({"type": "format", "range": f"H{r}:I{r}", "format": body_center})
        ops.append({"type": "row_height", "row": r, "height": 32})

    # Подзаголовок "ПО МЕСЯЦАМ" — строка 9
    ops.append({"type": "merge", "range": "A9:I9"})
    ops.append({"type": "format", "range": "A9:I9", "format": FMT_SUBHEADER})
    ops.append({"type": "row_height", "row": 9, "height": 28})

    # Заголовки таблицы 2 — строка 10
    ops.append({"type": "format", "range": "A10:I10", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 10, "height": 36})

    # Месяцы — строки 11-14
    for r in range(11, 15):
        ops.append({"type": "format", "range": f"A{r}", "format": body_label})
        ops.append({"type": "format", "range": f"B{r}:F{r}", "format": body_money})
        ops.append({"type": "format", "range": f"G{r}", "format": body_margin})
        ops.append({"type": "format", "range": f"H{r}:I{r}", "format": body_center})
        ops.append({"type": "row_height", "row": r, "height": 32})

    # Premium — строка 16
    premium_fmt = CellFormat(
        backgroundColor=SUBHEADER_BG,
        textFormat=TextFormat(fontSize=11, italic=True, foregroundColor=MUTED_FG),
        horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "merge", "range": "A16:I16"})
    ops.append({"type": "format", "range": "A16:I16", "format": premium_fmt})
    ops.append({"type": "row_height", "row": 16, "height": 26})

    # Ширины
    ops.append({"type": "width", "col": "A", "width": 140})
    ops.append({"type": "width", "col": "B", "width": 130})
    ops.append({"type": "width", "col": "C", "width": 130})
    ops.append({"type": "width", "col": "D", "width": 120})
    ops.append({"type": "width", "col": "E", "width": 130})
    ops.append({"type": "width", "col": "F", "width": 130})
    ops.append({"type": "width", "col": "G", "width": 100})
    ops.append({"type": "width", "col": "H", "width": 100})
    ops.append({"type": "width", "col": "I", "width": 120})

    ops.append({"type": "frozen", "rows": 4})

    # Примечания
    ops.append({"type": "note", "cell": "D4",
                "note": "Эффективная комиссия Ozon (после компенсации баллами). Ставка 2,81% от sale_price."})
    ops.append({"type": "note", "cell": "E4",
                "note": "Логистика, возвраты, эквайринг, прочие услуги. Без PremiumSubscription. Ставка 14,2%."})
    ops.append({"type": "note", "cell": "G4",
                "note": "Маржа = Прибыль / Выручка. Зелёный: 15%+, жёлтый: 5-15%, красный: менее 5%."})
    ops.append({"type": "note", "cell": "A4",
                "note": "«С 1 августа» — реальный бизнес. Июнь-июль — разогрев (8 и 5 заказов)."})

    n = batch_apply(ws, sid, ops)
    print(f"  Отправлено форматирований одним batch: {n}")

    # Цветной фон маржи в G5:G7 и G11:G14
    try:
        vals = ws.get("G5:G14")
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
            # пропускаем пустые строки (8, 9, 10)
            if r in (8, 9, 10):
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
            n2 = batch_apply(ws, sid, ops2)
            print(f"  Цвет маржи: {n2}")
    except Exception as e:
        print(f"  [WARN] Цвет маржи: {e}")
'''

pattern = re.compile(r"def format_money\(ws\):.*?(?=\n\ndef sync_money)", re.DOTALL)
src, n = pattern.subn(new_format_money + "\n\n", src)
print(f"[{'OK' if n else 'FAIL'}] format_money переписан")

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("\nГотово. Запускай: py sheets_sync.py")
