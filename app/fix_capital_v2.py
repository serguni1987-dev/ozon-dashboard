"""
fix_capital_v2.py — 4 фикса:
1. Резерв налога вынести из активов, добавить ЧИСТЫЕ АКТИВЫ
2. Переименовать "Вложили в закупку" → "Себестоимость проданного"
3. Прогноз 14 дней — 2 недели приходов
4. Добавить блок ВЫВОДЫ
"""
import re

src = open("sheets_sync.py", encoding="utf-8").read()

# Переписываем build_capital
new_build = '''def build_capital(con):
    """Блок КАПИТАЛ: где деньги, что забрать, прогноз, оборот."""

    # === Данные из БД ===
    last_input = con.execute("""
        SELECT update_date, on_account FROM capital_input
        ORDER BY update_date DESC LIMIT 1
    """).fetchone()
    if last_input:
        on_account = last_input[1] or 0
        input_date = last_input[0]
    else:
        on_account = 0
        input_date = "нет"

    # У Ozon к выплате (оценка)
    row = con.execute("""
        SELECT SUM(sale_price), SUM(sale_commission), SUM(bonus), SUM(coinvestment)
        FROM accruals
    """).fetchone()
    sale_sum = row[0] or 0
    comm_sum = row[1] or 0
    bonus_sum = row[2] or 0
    coinv_sum = row[3] or 0
    serv_sum = con.execute("SELECT SUM(amount) FROM accruals_services").fetchone()[0] or 0
    payouts_total = con.execute("SELECT SUM(amount) FROM payouts WHERE status = 'received'").fetchone()[0] or 0

    owed_by_ozon = sale_sum + comm_sum + bonus_sum + coinv_sum + serv_sum
    owed_by_ozon = max(0, owed_by_ozon - payouts_total)

    frozen = con.execute("""
        SELECT SUM(cs.total_present * p.cost_price)
        FROM current_stocks cs
        JOIN products p ON p.offer_id = cs.offer_id
        WHERE p.cost_price > 0 AND cs.total_present > 0
    """).fetchone()[0] or 0

    in_transit = 0

    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    date_from = (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")

    revenue_30 = con.execute(
        "SELECT SUM(revenue) FROM sales_daily WHERE date BETWEEN ? AND ?",
        (date_from, max_date)
    ).fetchone()[0] or 0

    cogs_30 = 0
    rows = con.execute("""
        SELECT p.cost_price, SUM(sd.orders_units) AS orders
        FROM sales_daily sd
        JOIN products p ON p.sku = sd.sku
        WHERE sd.date BETWEEN ? AND ?
        GROUP BY p.sku
    """, (date_from, max_date)).fetchall()
    for r in rows:
        cogs_30 += (r[0] or 0) * (r[1] or 0)

    profit_30 = revenue_30 * 0.088
    tax_reserve = profit_30 * 0.15

    total_assets = on_account + owed_by_ozon + frozen + in_transit
    net_assets = total_assets - tax_reserve

    # === ЧТО ЗАБРАТЬ ===
    reserve_proc = revenue_30 * 0.10
    reserve_fines = revenue_30 * 0.05
    free_money = on_account + owed_by_ozon - tax_reserve - reserve_proc - reserve_fines

    # === ПРОГНОЗ 14 ДНЕЙ ===
    today = datetime.now()
    payments = con.execute("""
        SELECT due_date, supplier, amount FROM procurement_plan
        WHERE status = 'planned' AND due_date BETWEEN ? AND ?
        ORDER BY due_date ASC
    """, (today.strftime("%Y-%m-%d"),
          (today + timedelta(days=14)).strftime("%Y-%m-%d"))).fetchall()

    # Приходы: 2 недели
    weekly_inflow = owed_by_ozon / 4 if owed_by_ozon else 0

    # === ОБОРОТ ===
    turnover = revenue_30 / cogs_30 if cogs_30 > 0 else 0
    days_per_turn = 30 / turnover if turnover > 0 else 0

    # === ВЫВОДЫ ===
    verdicts = []

    if free_money > 50000:
        verdicts.append(("✅", f"Свободно {free_money:,.0f} ₽ — можно забрать без вреда для бизнеса"))
    elif free_money > 10000:
        verdicts.append(("⚠", f"Свободно только {free_money:,.0f} ₽ — забирать осторожно"))
    else:
        verdicts.append(("❌", f"Свободных денег нет ({free_money:,.0f} ₽) — всё в резервах"))

    frozen_pct = frozen / total_assets * 100 if total_assets else 0
    if frozen_pct > 70:
        verdicts.append(("❌", f"{frozen_pct:.0f}% капитала в товаре — ускорить оборот"))
    elif frozen_pct > 50:
        verdicts.append(("⚠", f"{frozen_pct:.0f}% капитала в товаре — на грани"))
    else:
        verdicts.append(("✅", f"{frozen_pct:.0f}% капитала в товаре — оборот здоровый"))

    if owed_by_ozon > 50000:
        verdicts.append(("💰", f"У Ozon заморожено {owed_by_ozon:,.0f} ₽ — ждём выплат"))

    if days_per_turn > 30:
        verdicts.append(("⚠", f"Оборот {days_per_turn:.0f} дней — медленно, цель 15-20 дней"))
    elif days_per_turn > 0:
        potential = cogs_30 * (30 / 20 - 30 / days_per_turn) if days_per_turn > 0 else 0
        verdicts.append(("✅", f"Оборот {days_per_turn:.0f} дней — норма. Ускорить до 15 = +{potential:,.0f} ₽ свободных"))

    if tax_reserve > 0:
        verdicts.append(("📊", f"Резерв налога УСН: {tax_reserve:,.0f} ₽ — отложить до квартала"))

    # === Собираем data ===
    data = []
    data.append(["КАПИТАЛ - где деньги, что забрать", "", "", "", ""])
    data.append([f"актуально на {datetime.now().strftime('%d.%m.%Y %H:%M')}  |  данные из БД до {max_date}", "", "", "", ""])
    data.append(["", "", "", "", ""])

    # Блок 1. АКТИВЫ
    data.append(["1. ГДЕ ДЕНЬГИ (активы)", "", "", "", ""])
    data.append(["Место", "Сумма руб", "Доля %", "Комментарий", ""])
    data.append(["На счету", f"{on_account:,.0f}", f"{on_account/total_assets*100 if total_assets else 0:.1f}%",
                 f"обновлено {input_date}", ""])
    data.append(["У Ozon к выплате", f"{owed_by_ozon:,.0f}", f"{owed_by_ozon/total_assets*100 if total_assets else 0:.1f}%",
                 "оценка по начислениям", ""])
    data.append(["В товаре на складе", f"{frozen:,.0f}", f"{frozen/total_assets*100 if total_assets else 0:.1f}%",
                 "42 SKU с остатком", ""])
    data.append(["В товаре в пути", f"{in_transit:,.0f}", "0.0%",
                 "нет данных из API", ""])
    data.append(["ИТОГО АКТИВОВ", f"{total_assets:,.0f}", "100%", "", ""])
    data.append(["Резерв налога УСН 15%", f"-{tax_reserve:,.0f}", "",
                 "отложить на налог", ""])
    data.append(["ЧИСТЫЕ АКТИВЫ", f"{net_assets:,.0f}", "",
                 "за вычетом налога", ""])
    data.append(["", "", "", "", ""])

    # Блок 2. ЧТО ЗАБРАТЬ
    data.append(["2. ЧТО ЗАБРАТЬ (свободные деньги)", "", "", "", ""])
    data.append(["", "Сумма руб", "", "Комментарий", ""])
    data.append(["На счету + у Ozon", f"{on_account + owed_by_ozon:,.0f}", "",
                 "что можно получить", ""])
    data.append(["Резерв налога УСН", f"-{tax_reserve:,.0f}", "", "отложить на налог", ""])
    data.append(["Резерв закупок (10%)", f"-{reserve_proc:,.0f}", "",
                 "чтобы не остаться без товара", ""])
    data.append(["Резерв штрафов (5%)", f"-{reserve_fines:,.0f}", "",
                 "на риски и ошибки", ""])
    data.append(["МОЖНО ЗАБРАТЬ", f"{max(0, free_money):,.0f}", "",
                 "безопасно для бизнеса", ""])
    data.append(["", "", "", "", ""])

    # Блок 3. ПРОГНОЗ
    data.append(["3. КАССОВЫЙ ПРОГНОЗ (14 дней)", "", "", "", ""])
    data.append(["Что", "Когда", "Сумма руб", "", ""])
    data.append(["Приход от Ozon, неделя 1", "ожидается", "+" + f"{weekly_inflow:,.0f}",
                 "оценка", ""])
    data.append(["Приход от Ozon, неделя 2", "ожидается", "+" + f"{weekly_inflow:,.0f}",
                 "оценка", ""])
    if payments:
        for p in payments:
            data.append(["Платёж: " + (p[1] or "?"), p[0], f"-{p[2]:,.0f}", "", ""])
    else:
        data.append(["Платежи поставщикам", "нет плана", "0", "", ""])
    data.append(["Налог УСН (аванс)", "раз в квартал", "-" + f"{tax_reserve*3:,.0f}",
                 "оценка за квартал", ""])
    data.append(["", "", "", "", ""])

    # Блок 4. ОБОРОТ
    data.append(["4. ОБОРОТ ДЕНЕГ (за 30 дней)", "", "", "", ""])
    data.append(["Метрика", "Значение", "", "Комментарий", ""])
    data.append(["Себестоимость проданного", f"{cogs_30:,.0f} руб", "", "за 30 дней", ""])
    data.append(["Получили выручки", f"{revenue_30:,.0f} руб", "", "", ""])
    data.append(["Оборот", f"{turnover:.2f}x", "",
                 "во сколько раз прокрутился рубль", ""])
    data.append(["Дней на оборот", f"{days_per_turn:.0f}", "",
                 "вложил → получил", ""])
    data.append(["", "", "", "", ""])

    # Блок 5. ВЫВОДЫ
    data.append(["ВЫВОДЫ", "", "", "", ""])
    for icon, text in verdicts:
        data.append([icon + " " + text, "", "", "", ""])

    return data

'''

# Заменяем build_capital
pattern = re.compile(r"def build_capital\(con\):.*?(?=\ndef format_capital)", re.DOTALL)
src, n = pattern.subn(new_build + "\n\n", src)
print(f"[{'OK' if n else 'FAIL'}] build_capital переписан")

# Обновляем format_capital
new_fmt = '''def format_capital(ws):
    sid = ws.id
    ops = []
    ops.append({"type": "unmerge", "range": "A1:Z100"})
    ops.append({"type": "clear_notes", "range": "A1:Z100"})

    ops.append({"type": "merge", "range": "A1:E1"})
    ops.append({"type": "format", "range": "A1:E1", "format": FMT_TITLE})
    ops.append({"type": "row_height", "row": 1, "height": 40})

    sub_fmt = CellFormat(
        textFormat=TextFormat(fontSize=11, italic=True, foregroundColor=Color(0.35, 0.35, 0.35)),
        backgroundColor=SUBHEADER_BG,
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "merge", "range": "A2:E2"})
    ops.append({"type": "format", "range": "A2:E2", "format": sub_fmt})
    ops.append({"type": "row_height", "row": 2, "height": 26})

    section_fmt = CellFormat(
        backgroundColor=SUBHEADER_BG,
        textFormat=TextFormat(bold=True, fontSize=12, foregroundColor=Color(0.2, 0.2, 0.2)),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    tbl_hdr = CellFormat(
        backgroundColor=HEADER_BG,
        textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=HEADER_FG),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    label_fmt = CellFormat(
        textFormat=TextFormat(fontSize=11, bold=True),
        horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
    )
    value_fmt = CellFormat(
        textFormat=TextFormat(fontSize=11),
        horizontalAlignment='RIGHT', verticalAlignment='MIDDLE',
    )
    total_fmt = CellFormat(
        backgroundColor=Color(0.90, 0.94, 1.0),
        textFormat=TextFormat(fontSize=12, bold=True, foregroundColor=Color(0.10, 0.20, 0.50)),
        horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
    )
    total_val_fmt = CellFormat(
        backgroundColor=Color(0.90, 0.94, 1.0),
        textFormat=TextFormat(fontSize=12, bold=True, foregroundColor=Color(0.10, 0.20, 0.50)),
        horizontalAlignment='RIGHT', verticalAlignment='MIDDLE',
    )
    net_fmt = CellFormat(
        backgroundColor=Color(0.95, 0.98, 1.0),
        textFormat=TextFormat(fontSize=12, bold=True, foregroundColor=Color(0.10, 0.20, 0.50)),
        horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
    )
    net_val_fmt = CellFormat(
        backgroundColor=Color(0.95, 0.98, 1.0),
        textFormat=TextFormat(fontSize=12, bold=True, foregroundColor=Color(0.10, 0.20, 0.50)),
        horizontalAlignment='RIGHT', verticalAlignment='MIDDLE',
    )
    free_fmt = CellFormat(
        backgroundColor=GOOD_BG,
        textFormat=TextFormat(fontSize=13, bold=True, foregroundColor=GOOD_FG),
        horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
    )
    free_val_fmt = CellFormat(
        backgroundColor=GOOD_BG,
        textFormat=TextFormat(fontSize=13, bold=True, foregroundColor=GOOD_FG),
        horizontalAlignment='RIGHT', verticalAlignment='MIDDLE',
    )

    # === Блок 1. ГДЕ ДЕНЬГИ (строки 4-13) ===
    ops.append({"type": "merge", "range": "A4:E4"})
    ops.append({"type": "format", "range": "A4:E4", "format": section_fmt})
    ops.append({"type": "row_height", "row": 4, "height": 30})

    ops.append({"type": "format", "range": "A5:E5", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 5, "height": 32})

    # Строки 6-9 — активы (на счету, у Ozon, в товаре, в пути)
    for r in range(6, 10):
        ops.append({"type": "format", "range": f"A{r}", "format": label_fmt})
        ops.append({"type": "format", "range": f"B{r}:C{r}", "format": value_fmt})
        ops.append({"type": "row_height", "row": r, "height": 30})

    # Строка 10 — ИТОГО АКТИВОВ (синяя)
    ops.append({"type": "format", "range": "A10", "format": total_fmt})
    ops.append({"type": "format", "range": "B10:C10", "format": total_val_fmt})
    ops.append({"type": "row_height", "row": 10, "height": 30})

    # Строка 11 — Резерв налога (красный фон = вычет)
    minus_fmt = CellFormat(
        backgroundColor=Color(0xFF/255, 0xE5/255, 0xE5/255),
        textFormat=TextFormat(fontSize=11, bold=True, foregroundColor=BAD_FG),
        horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
    )
    minus_val_fmt = CellFormat(
        backgroundColor=Color(0xFF/255, 0xE5/255, 0xE5/255),
        textFormat=TextFormat(fontSize=11, bold=True, foregroundColor=BAD_FG),
        horizontalAlignment='RIGHT', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "format", "range": "A11", "format": minus_fmt})
    ops.append({"type": "format", "range": "B11:C11", "format": minus_val_fmt})
    ops.append({"type": "row_height", "row": 11, "height": 30})

    # Строка 12 — ЧИСТЫЕ АКТИВЫ
    ops.append({"type": "format", "range": "A12", "format": net_fmt})
    ops.append({"type": "format", "range": "B12:C12", "format": net_val_fmt})
    ops.append({"type": "row_height", "row": 12, "height": 30})

    # === Блок 2. ЧТО ЗАБРАТЬ (строки 14-20) ===
    ops.append({"type": "merge", "range": "A14:E14"})
    ops.append({"type": "format", "range": "A14:E14", "format": section_fmt})
    ops.append({"type": "row_height", "row": 14, "height": 30})

    ops.append({"type": "format", "range": "A15:E15", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 15, "height": 32})

    for r in range(16, 20):
        ops.append({"type": "format", "range": f"A{r}", "format": label_fmt})
        ops.append({"type": "format", "range": f"B{r}:C{r}", "format": value_fmt})
        ops.append({"type": "row_height", "row": r, "height": 30})

    # Строка 20 — МОЖНО ЗАБРАТЬ (зелёная)
    ops.append({"type": "format", "range": "A20", "format": free_fmt})
    ops.append({"type": "format", "range": "B20:C20", "format": free_val_fmt})
    ops.append({"type": "row_height", "row": 20, "height": 34})

    # === Блок 3. ПРОГНОЗ (строки 22-28) ===
    ops.append({"type": "merge", "range": "A22:E22"})
    ops.append({"type": "format", "range": "A22:E22", "format": section_fmt})
    ops.append({"type": "row_height", "row": 22, "height": 30})

    ops.append({"type": "format", "range": "A23:E23", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 23, "height": 32})

    for r in range(24, 29):
        ops.append({"type": "format", "range": f"A{r}", "format": label_fmt})
        ops.append({"type": "format", "range": f"B{r}", "format": CellFormat(
            textFormat=TextFormat(fontSize=11), horizontalAlignment='CENTER', verticalAlignment='MIDDLE')})
        ops.append({"type": "format", "range": f"C{r}", "format": value_fmt})
        ops.append({"type": "format", "range": f"D{r}", "format": CellFormat(
            textFormat=TextFormat(fontSize=10, italic=True, foregroundColor=MUTED_FG),
            horizontalAlignment='LEFT', verticalAlignment='MIDDLE')})
        ops.append({"type": "row_height", "row": r, "height": 28})

    # === Блок 4. ОБОРОТ (строки 30-34) ===
    ops.append({"type": "merge", "range": "A30:E30"})
    ops.append({"type": "format", "range": "A30:E30", "format": section_fmt})
    ops.append({"type": "row_height", "row": 30, "height": 30})

    ops.append({"type": "format", "range": "A31:E31", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 31, "height": 32})

    for r in range(32, 36):
        ops.append({"type": "format", "range": f"A{r}", "format": label_fmt})
        ops.append({"type": "format", "range": f"B{r}", "format": value_fmt})
        ops.append({"type": "format", "range": f"C{r}", "format": value_fmt})
        ops.append({"type": "format", "range": f"D{r}", "format": CellFormat(
            textFormat=TextFormat(fontSize=10, italic=True, foregroundColor=MUTED_FG),
            horizontalAlignment='LEFT', verticalAlignment='MIDDLE')})
        ops.append({"type": "row_height", "row": r, "height": 28})

    # === Блок 5. ВЫВОДЫ (строки 37+) ===
    ops.append({"type": "merge", "range": "A37:E37"})
    ops.append({"type": "format", "range": "A37:E37", "format": section_fmt})
    ops.append({"type": "row_height", "row": 37, "height": 30})

    # Строки выводов 38-44 (7 максимум) — merge A:E
    for r in range(38, 45):
        ops.append({"type": "merge", "range": f"A{r}:E{r}"})
        ops.append({"type": "row_height", "row": r, "height": 32})

    for c, w in [("A", 300), ("B", 140), ("C", 100), ("D", 260), ("E", 80)]:
        ops.append({"type": "width", "col": c, "width": w})

    ops.append({"type": "frozen", "rows": 2})

    n = batch_apply(ws, sid, ops)
    print(f"  Форматирование: {n}")

    # Цвет выводов
    try:
        vals = ws.get("A38:A44")
        ops2 = []
        for i, row in enumerate(vals):
            if not row:
                continue
            v = row[0]
            r = 38 + i
            if v.startswith("❌"):
                bg, fg = BAD_BG, BAD_FG
            elif v.startswith("⚠"):
                bg, fg = WARN_BG, Color(0.5, 0.4, 0)
            elif v.startswith("✅"):
                bg, fg = GOOD_BG, GOOD_FG
            elif v.startswith("💰"):
                bg, fg = Color(0.95, 0.95, 0.75), Color(0.5, 0.4, 0)
            elif v.startswith("📊"):
                bg, fg = Color(0.90, 0.94, 1.0), Color(0.10, 0.20, 0.50)
            else:
                bg, fg = SUBHEADER_BG, Color(0.2, 0.2, 0.2)
            ops2.append({"type": "format", "range": f"A{r}:E{r}", "format": CellFormat(
                backgroundColor=bg,
                textFormat=TextFormat(fontSize=11, foregroundColor=fg),
                horizontalAlignment='LEFT', verticalAlignment='MIDDLE', wrapStrategy='WRAP',
            )})
        if ops2:
            batch_apply(ws, sid, ops2)
            print(f"  Цвет выводов: {len(ops2)}")
    except Exception as e:
        print(f"  WARN: {e}")

'''

pattern = re.compile(r"def format_capital\(ws\):.*?(?=\ndef sync_capital)", re.DOTALL)
src, n = pattern.subn(new_fmt + "\n\n", src)
print(f"[{'OK' if n else 'FAIL'}] format_capital переписан")

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print()
print("Готово. Запускай: py sheets_sync.py")
