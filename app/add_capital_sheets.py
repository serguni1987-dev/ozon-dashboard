"""
add_capital_sheets.py — добавляет листы ВВОД и КАПИТАЛ в sheets_sync.py.
"""
src = open("sheets_sync.py", encoding="utf-8").read()

if "def sync_capital" in src:
    print("[i] sync_capital уже есть")
    exit(0)

new_code = '''
# ============ ЛИСТ ВВОД ============
def build_input(con):
    """Ручной ввод: остаток на счету, план закупок."""
    # Последний ввод остатка
    last_input = con.execute("""
        SELECT update_date, on_account, note FROM capital_input
        ORDER BY update_date DESC LIMIT 1
    """).fetchone()

    if last_input:
        update_date, on_account, note = last_input
    else:
        update_date, on_account, note = "", 0, ""

    # План закупок (активные, не оплаченные)
    procurements = con.execute("""
        SELECT id, due_date, supplier, amount, status
        FROM procurement_plan
        WHERE status = 'planned'
        ORDER BY due_date ASC
    """).fetchall()

    data = []
    data.append(["ВВОД ДАННЫХ", "", "", "", ""])
    data.append(["Заполняй раз в день/неделю. Значения идут в лист КАПИТАЛ.", "", "", "", ""])
    data.append(["", "", "", "", ""])
    data.append(["1. ОСТАТОК НА СЧЕТУ", "", "", "", ""])
    data.append(["Дата обновления (YYYY-MM-DD)", "Сумма на счету (руб)", "Комментарий", "", ""])
    data.append([update_date or "заполни", on_account or "", note or "", "", ""])
    data.append(["", "", "", "", ""])
    data.append(["2. ПЛАН ЗАКУПОК", "", "", "", ""])
    data.append(["Когда платить", "Кому", "Сколько руб", "Статус", "ID"])
    if procurements:
        for p in procurements:
            data.append([p["due_date"], p["supplier"] or "", p["amount"], p["status"], p["id"]])
    else:
        data.append(["пример: 2026-10-01", "Иванов (Сатин)", 50000, "planned", ""])
    data.append(["", "", "", "", ""])
    data.append(["3. ИНСТРУКЦИЯ", "", "", "", ""])
    data.append(["Как заполнять", "", "", "", ""])
    data.append(["Остаток на счету", "ЛК Ozon → Финансы → Баланс, или ваш банк", "", "", ""])
    data.append(["План закупок", "Кому/сколько/когда платить поставщику", "", "", ""])
    data.append(["После ввода", "Запусти: py calc_capital_to_db.py (сохранит в БД)", "", "", ""])
    return data


def format_input(ws):
    sid = ws.id
    ops = []
    ops.append({"type": "unmerge", "range": "A1:Z50"})
    ops.append({"type": "clear_notes", "range": "A1:Z50"})

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
    for r in [4, 8, 13]:
        ops.append({"type": "merge", "range": f"A{r}:E{r}"})
        ops.append({"type": "format", "range": f"A{r}:E{r}", "format": section_fmt})
        ops.append({"type": "row_height", "row": r, "height": 30})

    tbl_hdr = CellFormat(
        backgroundColor=HEADER_BG,
        textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=HEADER_FG),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    input_cell = CellFormat(
        backgroundColor=Color(0xFF/255, 0xF9/255, 0xD6/255),
        textFormat=TextFormat(bold=True, fontSize=12, foregroundColor=Color(0.2, 0.2, 0.2)),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )

    # 1. Остаток — заголовок и значение
    ops.append({"type": "format", "range": "A5:E5", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 5, "height": 32})
    ops.append({"type": "format", "range": "A6", "format": input_cell})
    ops.append({"type": "format", "range": "B6", "format": input_cell})
    ops.append({"type": "format", "range": "C6:E6", "format": input_cell})
    ops.append({"type": "row_height", "row": 6, "height": 40})

    # 2. План закупок — заголовок и данные
    ops.append({"type": "format", "range": "A9:E9", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 9, "height": 32})
    for r in range(10, 15):
        ops.append({"type": "row_height", "row": r, "height": 28})

    # 3. Инструкция
    body_left = CellFormat(
        textFormat=TextFormat(fontSize=11),
        horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
        wrapStrategy='WRAP',
    )
    for r in range(14, 18):
        ops.append({"type": "format", "range": f"A{r}:E{r}", "format": body_left})
        ops.append({"type": "row_height", "row": r, "height": 28})

    for c, w in [("A", 240), ("B", 200), ("C", 160), ("D", 120), ("E", 80)]:
        ops.append({"type": "width", "col": c, "width": w})

    ops.append({"type": "frozen", "rows": 2})

    ops.append({"type": "note", "cell": "B6",
                "note": "Открой ЛК Ozon - Финансы - Баланс. Скопируй сумму сюда. Раз в день."})
    ops.append({"type": "note", "cell": "A6",
                "note": "Введи сегодняшнюю дату в формате 2026-09-21"})
    ops.append({"type": "note", "cell": "A9",
                "note": "Строки для плана закупок. Одна строка = одна оплата поставщику."})

    n = batch_apply(ws, sid, ops)
    print(f"  Форматирование: {n}")


def sync_input(sh, con):
    print("")
    print("[Лист ВВОД]")
    ws = get_or_create_sheet(sh, "ВВОД")
    data = build_input(con)
    clear_and_write(ws, data)
    print(f"  Записано строк: {len(data)}")
    format_input(ws)


# ============ ЛИСТ КАПИТАЛ ============
def build_capital(con):
    """Блок КАПИТАЛ: где деньги, что забрать, прогноз, оборот."""

    # === 1. ГДЕ ДЕНЬГИ ===
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
        SELECT
            SUM(sale_price) AS sale,
            SUM(sale_commission) AS comm,
            SUM(bonus) AS bonus,
            SUM(coinvestment) AS coinv
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

    # В товаре
    frozen = con.execute("""
        SELECT SUM(cs.total_present * p.cost_price)
        FROM current_stocks cs
        JOIN products p ON p.offer_id = cs.offer_id
        WHERE p.cost_price > 0 AND cs.total_present > 0
    """).fetchone()[0] or 0

    # В пути (пока 0)
    in_transit = 0

    # Прибыль за 30 дней (для налога)
    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    date_from = (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")

    revenue_30 = con.execute(
        "SELECT SUM(revenue) FROM sales_daily WHERE date BETWEEN ? AND ?",
        (date_from, max_date)
    ).fetchone()[0] or 0

    # Себестоимость проданного за 30 дней
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

    total_money = on_account + owed_by_ozon + frozen + in_transit

    # === 2. ЧТО ЗАБРАТЬ ===
    reserve_proc = revenue_30 * 0.10
    reserve_fines = revenue_30 * 0.05
    free_money = on_account + owed_by_ozon - tax_reserve - reserve_proc - reserve_fines

    # === 3. ПРОГНОЗ 14 ДНЕЙ ===
    today = datetime.now()
    payments = con.execute("""
        SELECT due_date, supplier, amount FROM procurement_plan
        WHERE status = 'planned' AND due_date BETWEEN ? AND ?
        ORDER BY due_date ASC
    """, (today.strftime("%Y-%m-%d"),
          (today + timedelta(days=14)).strftime("%Y-%m-%d"))).fetchall()

    # === 4. ОБОРОТ ===
    turnover = revenue_30 / cogs_30 if cogs_30 > 0 else 0
    days_per_turn = 30 / turnover if turnover > 0 else 0

    # === Собираем data ===
    data = []
    data.append(["КАПИТАЛ - где деньги, что забрать", "", "", "", ""])
    data.append([f"актуально на {datetime.now().strftime('%d.%m.%Y %H:%M')}  |  данные из БД до {max_date}", "", "", "", ""])
    data.append(["", "", "", "", ""])

    # Блок 1. ГДЕ ДЕНЬГИ
    data.append(["1. ГДЕ ДЕНЬГИ", "", "", "", ""])
    data.append(["Место", "Сумма руб", "Доля %", "Комментарий", ""])
    data.append(["На счету", f"{on_account:,.0f}", f"{on_account/total_money*100 if total_money else 0:.1f}%",
                 f"обновлено {input_date}", ""])
    data.append(["У Ozon к выплате", f"{owed_by_ozon:,.0f}", f"{owed_by_ozon/total_money*100 if total_money else 0:.1f}%",
                 "оценка по начислениям", ""])
    data.append(["В товаре на складе", f"{frozen:,.0f}", f"{frozen/total_money*100 if total_money else 0:.1f}%",
                 "42 SKU с остатком", ""])
    data.append(["В товаре в пути", f"{in_transit:,.0f}", "0.0%",
                 "нужны данные из API", ""])
    data.append(["Резерв налога УСН 15%", f"{tax_reserve:,.0f}", "",
                 "от прибыли за 30 дней", ""])
    data.append(["ВСЕГО ДЕНЕГ", f"{total_money:,.0f}", "100%", "", ""])
    data.append(["", "", "", "", ""])

    # Блок 2. ЧТО ЗАБРАТЬ
    data.append(["2. ЧТО ЗАБРАТЬ (свободные деньги)", "", "", "", ""])
    data.append(["", "Сумма руб", "", "Комментарий", ""])
    data.append(["На счету + у Ozon", f"{on_account + owed_by_ozon:,.0f}", "",
                 "то, что можно получить", ""])
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
    data.append(["Приход от Ozon", "ожидается", "~" + f"{owed_by_ozon/4:,.0f}",
                 "оценка: /4 (раз в неделю)", ""])
    if payments:
        for p in payments:
            data.append(["Платёж поставщику: " + (p[1] or "?"),
                         p[0], f"-{p[2]:,.0f}", "", ""])
    else:
        data.append(["Платежи поставщикам", "нет плана", "0", "", ""])
    data.append(["Налог УСН (аванс)", "раз в квартал", "~" + f"{tax_reserve*3:,.0f}",
                 "оценка за квартал", ""])
    data.append(["", "", "", "", ""])

    # Блок 4. ОБОРОТ
    data.append(["4. ОБОРОТ ДЕНЕГ (за 30 дней)", "", "", "", ""])
    data.append(["Метрика", "Значение", "", "Комментарий", ""])
    data.append(["Вложили в закупку", f"{cogs_30:,.0f} руб", "", "себестоимость проданного", ""])
    data.append(["Получили выручки", f"{revenue_30:,.0f} руб", "", "", ""])
    data.append(["Оборот", f"{turnover:.2f}x", "",
                 "во сколько раз прокрутился рубль", ""])
    data.append(["Дней на оборот", f"{days_per_turn:.0f}", "",
                 "вложил → получил", ""])
    return data


def format_capital(ws):
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
    # Заголовки блоков
    for r in [4, 12, 20, 27]:
        ops.append({"type": "merge", "range": f"A{r}:E{r}"})
        ops.append({"type": "format", "range": f"A{r}:E{r}", "format": section_fmt})
        ops.append({"type": "row_height", "row": r, "height": 30})

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

    # Блок 1: ГДЕ ДЕНЬГИ
    ops.append({"type": "format", "range": "A5:E5", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 5, "height": 32})
    for r in range(6, 12):
        ops.append({"type": "format", "range": f"A{r}", "format": label_fmt})
        ops.append({"type": "format", "range": f"B{r}:C{r}", "format": value_fmt})
        ops.append({"type": "row_height", "row": r, "height": 30})
    # Строка ВСЕГО — выделить
    ops.append({"type": "format", "range": "A11", "format": total_fmt})
    ops.append({"type": "format", "range": "B11:C11", "format": total_val_fmt})

    # Блок 2: ЧТО ЗАБРАТЬ
    ops.append({"type": "format", "range": "A13:E13", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 13, "height": 32})
    for r in range(14, 19):
        ops.append({"type": "format", "range": f"A{r}", "format": label_fmt})
        ops.append({"type": "format", "range": f"B{r}:C{r}", "format": value_fmt})
        ops.append({"type": "row_height", "row": r, "height": 30})
    # Строка МОЖНО ЗАБРАТЬ — зелёная
    ops.append({"type": "format", "range": "A18", "format": free_fmt})
    ops.append({"type": "format", "range": "B18:C18", "format": free_val_fmt})

    # Блок 3: ПРОГНОЗ
    ops.append({"type": "format", "range": "A21:E21", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 21, "height": 32})
    for r in range(22, 28):
        ops.append({"type": "row_height", "row": r, "height": 28})

    # Блок 4: ОБОРОТ
    ops.append({"type": "format", "range": "A28:E28", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 28, "height": 32})
    for r in range(29, 33):
        ops.append({"type": "row_height", "row": r, "height": 28})

    for c, w in [("A", 280), ("B", 140), ("C", 100), ("D", 260), ("E", 80)]:
        ops.append({"type": "width", "col": c, "width": w})

    ops.append({"type": "frozen", "rows": 2})

    ops.append({"type": "note", "cell": "A6",
                "note": "Сколько на расчетном счету. Заполни лист ВВОД."})
    ops.append({"type": "note", "cell": "A7",
                "note": "Оценка: что Ozon должен выплатить по начислениям за период."})
    ops.append({"type": "note", "cell": "A8",
                "note": "Деньги, вложенные в товар, лежащий на складе Ozon."})
    ops.append({"type": "note", "cell": "A18",
                "note": "На счету + у Ozon - резервы на налог, закупки и штрафы."})

    n = batch_apply(ws, sid, ops)
    print(f"  Форматирование: {n}")


def sync_capital(sh, con):
    print("")
    print("[Лист КАПИТАЛ]")
    ws = get_or_create_sheet(sh, "КАПИТАЛ")
    data = build_capital(con)
    clear_and_write(ws, data)
    print(f"  Записано строк: {len(data)}")
    format_capital(ws)

'''

# Вставляем перед def main
if "def main():" in src:
    src = src.replace("def main():", new_code + "\ndef main():", 1)
    print("[OK] Функции добавлены")

# В main — вызываем sync_input и sync_capital
old_main = "    sync_manual(sh, con)"
new_main = "    sync_manual(sh, con)\n    sync_input(sh, con)\n    sync_capital(sh, con)"
if old_main in src:
    src = src.replace(old_main, new_main, 1)
    print("[OK] sync_input и sync_capital добавлены в main")

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("")
print("Готово. Запускай: py sheets_sync.py")
