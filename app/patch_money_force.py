"""
patch_money_force.py — принудительно заменяет build_money и format_money.
"""
import re

src = open("sheets_sync.py", encoding="utf-8").read()

# Проверка: есть ли «ВЫВОДЫ» в build_money?
if '"ВЫВОДЫ"' in src or "'ВЫВОДЫ'" in src:
    print("[i] «ВЫВОДЫ» уже в коде")
else:
    print("[!] «ВЫВОДЫ» НЕ в коде — патч не применился")

# Показываем границы текущего build_money
m = re.search(r"def build_money\(con\):.*?(?=\ndef )", src, re.DOTALL)
if m:
    print(f"[i] Текущий build_money: {len(m.group(0))} символов")
    # Последние 200 символов
    print("[i] Конец build_money:")
    print(m.group(0)[-300:])

# Удаляем build_money
src = re.sub(r"def build_money\(con\):.*?(?=\ndef )", "", src, flags=re.DOTALL)
print("[OK] Старый build_money удалён")

# Удаляем format_money
src = re.sub(r"def format_money\(ws\):.*?(?=\n\ndef sync_money)", "", src, flags=re.DOTALL)
print("[OK] Старый format_money удалён")

# Удаляем sync_money
src = re.sub(r"def sync_money\(sh, con\):.*?(?=\n\ndef build_result)", "", src, flags=re.DOTALL)
print("[OK] Старый sync_money удалён")

# Вставляем новые версии перед build_result
new_block = '''def build_money(con):
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

    period_stats = {}
    for label, d1, d2 in periods:
        stats = calc_period(d1, d2)
        period_stats[label] = stats
        rev, cost, comm, serv, profit, margin, orders, avg = stats
        data.append([
            label,
            f"{rev:,.0f}", f"{cost:,.0f}", f"{comm:,.0f}", f"{serv:,.0f}",
            f"{profit:,.0f}", f"{margin*100:.1f}%", orders, f"{avg:,.0f}",
        ])

    # Легенда
    data.append([
        "Что значит: Комиссия — эффективная (после баллов). "
        "Услуги Ozon — логистика, возвраты, эквайринг. "
        "Маржа = Прибыль / Выручка. Premium — постоянный расход, не в марже.",
        "", "", "", "", "", "", "", ""
    ])
    data.append(["", "", "", "", "", "", "", "", ""])

    # ПО МЕСЯЦАМ
    data.append(["ПО МЕСЯЦАМ", "", "", "", "", "", "", "", ""])
    data.append(["Месяц", "Выручка", "Себестоимость", "Комиссия", "Услуги Ozon",
                 "Прибыль", "Маржа", "Заказов", "Ср. чек"])

    months = con.execute("""
        SELECT substr(date, 1, 7) AS m, MIN(date), MAX(date)
        FROM sales_daily GROUP BY m ORDER BY m DESC
    """).fetchall()

    month_stats = {}
    for m, d1, d2 in months:
        stats = calc_period(d1, d2)
        month_stats[m] = stats
        rev, cost, comm, serv, profit, margin, orders, avg = stats
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

    # ВЫВОДЫ
    data.append(["ВЫВОДЫ", "", "", "", "", "", "", "", ""])

    s30 = period_stats["30 дней"]
    margin_30 = s30[5]
    cost_pct_30 = s30[1] / s30[0] if s30[0] else 0
    serv_pct_30 = s30[4] / s30[0] if s30[0] else 0

    if margin_30 < 0.05:
        v1 = f"❌ Критично: маржа {margin_30*100:.1f}% — работаем почти в ноль"
    elif margin_30 < 0.10:
        v1 = f"⚠ Тонко: маржа {margin_30*100:.1f}% — любой сбой уводит в минус"
    elif margin_30 < 0.15:
        v1 = f"✅ Норма: маржа {margin_30*100:.1f}% — есть куда расти"
    else:
        v1 = f"🟢 Отлично: маржа {margin_30*100:.1f}%"

    aug = month_stats.get("2026-08")
    sep = month_stats.get("2026-09")
    if aug and sep:
        d_margin = (sep[5] - aug[5]) * 100
        if d_margin < -1:
            v2 = (f"⚠ Падение маржи: сентябрь {sep[5]*100:.1f}% vs август {aug[5]*100:.1f}% "
                  f"({d_margin:+.1f} п.п.) — разобраться с убыточными SKU")
        elif d_margin > 1:
            v2 = f"✅ Рост маржи: {aug[5]*100:.1f}% → {sep[5]*100:.1f}% ({d_margin:+.1f} п.п.)"
        else:
            v2 = f"➖ Маржа стабильна: {sep[5]*100:.1f}% (было {aug[5]*100:.1f}%)"
    else:
        v2 = "Динамика: недостаточно данных"

    if cost_pct_30 > 0.75:
        v3 = f"❌ Себестоимость съедает {cost_pct_30*100:.0f}% выручки — главный рычаг роста"
    elif cost_pct_30 > 0.65:
        v3 = f"⚠ Себестоимость {cost_pct_30*100:.0f}% — торговаться с поставщиком"
    else:
        v3 = f"✅ Себестоимость {cost_pct_30*100:.0f}% — приемлемо"

    if serv_pct_30 > 0.15:
        v4 = f"⚠ Услуги Ozon {serv_pct_30*100:.1f}% — проверить логистику и возвраты"
    else:
        v4 = f"✅ Услуги Ozon {serv_pct_30*100:.1f}% — в норме"

    from plan_core import get_actions
    month_ago = (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")
    actions = get_actions(con, month_ago, max_date)
    if actions:
        top = actions[0]
        total_effect = sum(a["effect"] for a in actions)
        v5 = (f"→ Действия: {top['offer_id']} ({top['category']}, "
              f"{top['effect']:,.0f} ₽), всего {len(actions)} SKU, "
              f"потенциал {total_effect:,.0f} ₽/мес")
    else:
        v5 = "→ Действий нет"

    data.append([v1, "", "", "", "", "", "", "", ""])
    data.append([v2, "", "", "", "", "", "", "", ""])
    data.append([v3, "", "", "", "", "", "", "", ""])
    data.append([v4, "", "", "", "", "", "", "", ""])
    data.append([v5, "", "", "", "", "", "", "", ""])

    data.append(["", "", "", "", "", "", "", "", ""])
    data.append([f"PremiumSubscription {PREMIUM_FIXED:,.0f} ₽/мес — постоянный расход, не в марже",
                 "", "", "", "", "", "", "", ""])
    return data


def format_money(ws):
    sid = ws.id
    ops = []

    ops.append({"type": "unmerge", "range": "A1:Z50"})
    ops.append({"type": "clear_notes", "range": "A1:Z50"})

    ops.append({"type": "merge", "range": "A1:I1"})
    ops.append({"type": "format", "range": "A1:I1", "format": FMT_TITLE})
    ops.append({"type": "row_height", "row": 1, "height": 40})

    sub_fmt = CellFormat(
        textFormat=TextFormat(fontSize=11, italic=True, foregroundColor=Color(0.35, 0.35, 0.35)),
        backgroundColor=SUBHEADER_BG,
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "merge", "range": "A2:I2"})
    ops.append({"type": "format", "range": "A2:I2", "format": sub_fmt})
    ops.append({"type": "row_height", "row": 2, "height": 26})

    tbl_hdr = CellFormat(
        backgroundColor=HEADER_BG,
        textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=HEADER_FG),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "format", "range": "A4:I4", "format": tbl_hdr})
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

    for r in range(5, 8):
        ops.append({"type": "format", "range": f"A{r}", "format": body_label})
        ops.append({"type": "format", "range": f"B{r}:F{r}", "format": body_money})
        ops.append({"type": "format", "range": f"G{r}", "format": body_margin})
        ops.append({"type": "format", "range": f"H{r}:I{r}", "format": body_center})
        ops.append({"type": "row_height", "row": r, "height": 32})

    # Легенда — строка 8
    legend_fmt = CellFormat(
        textFormat=TextFormat(fontSize=9, italic=True, foregroundColor=MUTED_FG),
        backgroundColor=Color(0.98, 0.98, 0.98),
        horizontalAlignment='LEFT', verticalAlignment='MIDDLE', wrapStrategy='WRAP',
    )
    ops.append({"type": "merge", "range": "A8:I8"})
    ops.append({"type": "format", "range": "A8:I8", "format": legend_fmt})
    ops.append({"type": "row_height", "row": 8, "height": 30})

    # ПО МЕСЯЦАМ — строка 10
    ops.append({"type": "merge", "range": "A10:I10"})
    ops.append({"type": "format", "range": "A10:I10", "format": FMT_SUBHEADER})
    ops.append({"type": "row_height", "row": 10, "height": 28})

    ops.append({"type": "format", "range": "A11:I11", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 11, "height": 36})

    for r in range(12, 16):
        ops.append({"type": "format", "range": f"A{r}", "format": body_label})
        ops.append({"type": "format", "range": f"B{r}:F{r}", "format": body_money})
        ops.append({"type": "format", "range": f"G{r}", "format": body_margin})
        ops.append({"type": "format", "range": f"H{r}:I{r}", "format": body_center})
        ops.append({"type": "row_height", "row": r, "height": 32})

    # ВЫВОДЫ — строка 17
    ops.append({"type": "merge", "range": "A17:I17"})
    ops.append({"type": "format", "range": "A17:I17", "format": FMT_SUBHEADER})
    ops.append({"type": "row_height", "row": 17, "height": 28})

    # Выводы 18-22
    for r in range(18, 23):
        ops.append({"type": "merge", "range": f"A{r}:I{r}"})
        ops.append({"type": "row_height", "row": r, "height": 30})

    # Premium — строка 24
    premium_fmt = CellFormat(
        backgroundColor=SUBHEADER_BG,
        textFormat=TextFormat(fontSize=11, italic=True, foregroundColor=MUTED_FG),
        horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "merge", "range": "A24:I24"})
    ops.append({"type": "format", "range": "A24:I24", "format": premium_fmt})
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

    ops.append({"type": "frozen", "rows": 4})

    ops.append({"type": "note", "cell": "D4",
                "note": "Эффективная комиссия Ozon (после компенсации баллами). 2,81% от sale_price."})
    ops.append({"type": "note", "cell": "E4",
                "note": "Логистика, возвраты, эквайринг. 14,2% от sale_price. Без Premium."})
    ops.append({"type": "note", "cell": "G4",
                "note": "Маржа = Прибыль / Выручка. Зелёный: 15%+, жёлтый: 5-15%, красный: <5%."})

    n = batch_apply(ws, sid, ops)
    print(f"  Основное форматирование: {n}")

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

    # Цвет выводов 18-22
    try:
        vals = ws.get("A18:A22")
        ops3 = []
        for i, row in enumerate(vals):
            if not row:
                continue
            v = row[0]
            r = 18 + i
            if v.startswith("❌") or v.startswith("⚠"):
                bg, fg = BAD_BG, BAD_FG
            elif v.startswith("✅") or v.startswith("🟢"):
                bg, fg = GOOD_BG, GOOD_FG
            else:
                bg, fg = SUBHEADER_BG, Color(0.2, 0.2, 0.2)
            ops3.append({"type": "format", "range": f"A{r}:I{r}", "format": CellFormat(
                backgroundColor=bg,
                textFormat=TextFormat(fontSize=11, foregroundColor=fg),
                horizontalAlignment='LEFT', verticalAlignment='MIDDLE', wrapStrategy='WRAP',
            )})
        if ops3:
            n3 = batch_apply(ws, sid, ops3)
            print(f"  Цвет выводов: {n3}")
    except Exception as e:
        print(f"  [WARN] Цвет выводов: {e}")


def sync_money(sh, con):
    print("\\n[Лист ДЕНЬГИ]")
    ws = get_or_create_sheet(sh, "ДЕНЬГИ")
    data = build_money(con)
    clear_and_write(ws, data)
    print(f"  Записано строк: {len(data)}")
    format_money(ws)


'''

# Вставляем перед def build_result
anchor = "def build_result(con):"
if anchor in src:
    src = src.replace(anchor, new_block + anchor, 1)
    print("[OK] Новые функции вставлены")
else:
    print("[FAIL] Не нашёл build_result")

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("\nГотово. Запускай: py sheets_sync.py")
