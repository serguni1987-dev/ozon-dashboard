"""
patch_money_result_format.py — форматирование листов ДЕНЬГИ и РЕЗУЛЬТАТ.
"""
src = open("sheets_sync.py", encoding="utf-8").read()

# ============ ФУНКЦИЯ format_money ============
format_money_code = '''

def format_money(ws):
    sid = ws.id
    ops = []

    # Сброс
    ops.append({"type": "unmerge", "range": "A1:Z50"})
    ops.append({"type": "clear_notes", "range": "A1:Z50"})

    # Заголовок A1:I1
    ops.append({"type": "merge", "range": "A1:I1"})
    ops.append({"type": "format", "range": "A1:I1", "format": FMT_TITLE})
    ops.append({"type": "row_height", "row": 1, "height": 40})

    # Подзаголовок A2:I2 — со ставками
    sub_fmt = CellFormat(
        textFormat=TextFormat(bold=False, fontSize=11, italic=True,
                              foregroundColor=Color(0.35, 0.35, 0.35)),
        backgroundColor=SUBHEADER_BG,
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "merge", "range": "A2:I2"})
    ops.append({"type": "format", "range": "A2:I2", "format": sub_fmt})
    ops.append({"type": "row_height", "row": 2, "height": 26})

    # Заголовки таблицы — строка 4
    tbl_hdr = CellFormat(
        backgroundColor=HEADER_BG,
        textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=HEADER_FG),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "format", "range": "A4:I4", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 4, "height": 36})

    # Данные 5-7 — периоды
    body = CellFormat(
        textFormat=TextFormat(fontSize=11),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    body_label = CellFormat(
        textFormat=TextFormat(fontSize=11, bold=True),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
        backgroundColor=SUBHEADER_BG,
    )
    body_money = CellFormat(
        textFormat=TextFormat(fontSize=11),
        horizontalAlignment='RIGHT', verticalAlignment='MIDDLE',
    )
    body_profit = CellFormat(
        textFormat=TextFormat(fontSize=12, bold=True),
        horizontalAlignment='RIGHT', verticalAlignment='MIDDLE',
    )
    body_margin = CellFormat(
        textFormat=TextFormat(fontSize=12, bold=True),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )

    for r in range(5, 8):
        ops.append({"type": "format", "range": f"A{r}", "format": body_label})
        ops.append({"type": "format", "range": f"B{r}:F{r}", "format": body_money})
        ops.append({"type": "format", "range": f"G{r}", "format": body_profit})
        ops.append({"type": "format", "range": f"H{r}:I{r}", "format": body})
        ops.append({"type": "format", "range": f"G{r}", "format": body_margin})
        ops.append({"type": "row_height", "row": r, "height": 32})

    # PremiumSubscription — строка 9-10
    premium_fmt = CellFormat(
        backgroundColor=SUBHEADER_BG,
        textFormat=TextFormat(fontSize=11, italic=True, foregroundColor=MUTED_FG),
        horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "merge", "range": "A9:I9"})
    ops.append({"type": "format", "range": "A9:I9", "format": premium_fmt})
    ops.append({"type": "row_height", "row": 9, "height": 26})

    # Ширины
    ops.append({"type": "width", "col": "A", "width": 140})  # Период
    ops.append({"type": "width", "col": "B", "width": 130})  # Выручка
    ops.append({"type": "width", "col": "C", "width": 130})  # Себест
    ops.append({"type": "width", "col": "D", "width": 120})  # Комиссия
    ops.append({"type": "width", "col": "E", "width": 130})  # Услуги
    ops.append({"type": "width", "col": "F", "width": 130})  # Прибыль
    ops.append({"type": "width", "col": "G", "width": 100})  # Маржа
    ops.append({"type": "width", "col": "H", "width": 100})  # Заказов
    ops.append({"type": "width", "col": "I", "width": 120})  # Ср. чек

    ops.append({"type": "frozen", "rows": 4})

    # Примечания
    ops.append({"type": "note", "cell": "D4",
                "note": "Эффективная комиссия Ozon (после компенсации баллами). Ставка 2,81% от sale_price."})
    ops.append({"type": "note", "cell": "E4",
                "note": "Логистика, возвраты, эквайринг, прочие услуги. Без PremiumSubscription. Ставка 14,2% от sale_price."})
    ops.append({"type": "note", "cell": "G4",
                "note": "Маржа = Прибыль / Выручка. Зелёный: 15%+, жёлтый: 5-15%, красный: менее 5%."})
    ops.append({"type": "note", "cell": "F4",
                "note": "Прибыль после налога УСН 15%."})

    n = batch_apply(ws, sid, ops)
    print(f"  Отправлено форматирований одним batch: {n}")

    # Условное форматирование маржи — отдельным запросом через conditional_format
    try:
        from gspread_formatting import conditional_format_rule, ConditionalFormatRule, BooleanRule, BooleanCondition
        rules = [
            # Маржа < 5% — красный (значение уже в процентах: 0.06 = 6%)
            ConditionalFormatRule(
                ranges=[__import__("gspread").utils.absolute_range_name(ws.title, "G5:G7")],
                booleanRule=BooleanRule(
                    condition=BooleanCondition("NUMBER_LESS", ["0.05"]),
                    format=CellFormat(backgroundColor=BAD_BG,
                                      textFormat=TextFormat(bold=True, foregroundColor=BAD_FG)),
                ),
            ),
            ConditionalFormatRule(
                ranges=[__import__("gspread").utils.absolute_range_name(ws.title, "G5:G7")],
                booleanRule=BooleanRule(
                    condition=BooleanCondition("NUMBER_BETWEEN", ["0.05", "0.15"]),
                    format=CellFormat(backgroundColor=WARN_BG,
                                      textFormat=TextFormat(bold=True, foregroundColor=Color(0.5, 0.4, 0.0))),
                ),
            ),
            ConditionalFormatRule(
                ranges=[__import__("gspread").utils.absolute_range_name(ws.title, "G5:G7")],
                booleanRule=BooleanRule(
                    condition=BooleanCondition("NUMBER_GREATER", ["0.15"]),
                    format=CellFormat(backgroundColor=GOOD_BG,
                                      textFormat=TextFormat(bold=True, foregroundColor=GOOD_FG)),
                ),
            ),
        ]
        set_data_validation = None  # placeholder
        ws.spreadsheet.batch_update({"requests": [
            {"addConditionalFormatRule": {"rule": r.to_props()[0] if hasattr(r, "to_props") else r, "index": 0}}
            for r in rules
        ]})
        print("  Условное форматирование маржи применено")
    except Exception as e:
        print(f"  [WARN] Условное форматирование маржи не применилось: {e}")


def sync_money(sh, con):
    print("\\n[Лист ДЕНЬГИ]")
    ws = get_or_create_sheet(sh, "ДЕНЬГИ")
    data = build_money(con)
    clear_and_write(ws, data)
    print(f"  Записано строк: {len(data)}")
    format_money(ws)


# ============ ФУНКЦИЯ format_result ============

def format_result(ws):
    sid = ws.id
    ops = []

    ops.append({"type": "unmerge", "range": "A1:Z50"})
    ops.append({"type": "clear_notes", "range": "A1:Z50"})

    # Заголовок A1:D1
    ops.append({"type": "merge", "range": "A1:D1"})
    ops.append({"type": "format", "range": "A1:D1", "format": FMT_TITLE})
    ops.append({"type": "row_height", "row": 1, "height": 40})

    # Подзаголовок A2:D2
    sub_fmt = CellFormat(
        textFormat=TextFormat(fontSize=11, italic=True, foregroundColor=Color(0.35, 0.35, 0.35)),
        backgroundColor=SUBHEADER_BG,
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "merge", "range": "A2:D2"})
    ops.append({"type": "format", "range": "A2:D2", "format": sub_fmt})
    ops.append({"type": "row_height", "row": 2, "height": 26})

    # Заголовки — строка 4
    tbl_hdr = CellFormat(
        backgroundColor=HEADER_BG,
        textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=HEADER_FG),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "format", "range": "A4:D4", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": 4, "height": 36})

    # Данные 5-9
    body_label = CellFormat(
        textFormat=TextFormat(fontSize=11, bold=True),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
        backgroundColor=SUBHEADER_BG,
    )
    body_val = CellFormat(
        textFormat=TextFormat(fontSize=11),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    body_delta = CellFormat(
        textFormat=TextFormat(fontSize=11, bold=True),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )

    for r in range(5, 10):
        ops.append({"type": "format", "range": f"A{r}", "format": body_label})
        ops.append({"type": "format", "range": f"B{r}:C{r}", "format": body_val})
        ops.append({"type": "format", "range": f"D{r}", "format": body_delta})
        ops.append({"type": "row_height", "row": r, "height": 32})

    # Прошлый запуск — строка 11
    last_run = CellFormat(
        textFormat=TextFormat(fontSize=10, italic=True, foregroundColor=MUTED_FG),
        horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "merge", "range": "A11:D11"})
    ops.append({"type": "format", "range": "A11:D11", "format": last_run})
    ops.append({"type": "row_height", "row": 11, "height": 24})

    # Ширины
    ops.append({"type": "width", "col": "A", "width": 180})
    ops.append({"type": "width", "col": "B", "width": 160})
    ops.append({"type": "width", "col": "C", "width": 160})
    ops.append({"type": "width", "col": "D", "width": 120})

    ops.append({"type": "frozen", "rows": 4})

    # Примечания
    ops.append({"type": "note", "cell": "D4",
                "note": "Δ = изменение vs прошлый запуск. Зелёный: рост, красный: падение."})

    n = batch_apply(ws, sid, ops)
    print(f"  Отправлено форматирований одним batch: {n}")

    # Δ-цвета (по значениям, не условным форматированием — просто форматируем вручную)
    # Читаем значения D5:D9 и раскрашиваем
    try:
        values = ws.get("D5:D9")
        ops2 = []
        for i, row in enumerate(values):
            if not row:
                continue
            v = row[0].strip()
            r = 5 + i
            if v.startswith("+") and any(c.isdigit() for c in v):
                ops2.append({"type": "format", "range": f"D{r}", "format": CellFormat(
                    backgroundColor=GOOD_BG,
                    textFormat=TextFormat(fontSize=11, bold=True, foregroundColor=GOOD_FG),
                    horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
                )})
            elif v.startswith("-") and any(c.isdigit() for c in v):
                ops2.append({"type": "format", "range": f"D{r}", "format": CellFormat(
                    backgroundColor=BAD_BG,
                    textFormat=TextFormat(fontSize=11, bold=True, foregroundColor=BAD_FG),
                    horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
                )})
        if ops2:
            n2 = batch_apply(ws, sid, ops2)
            print(f"  Δ-цвета применены: {n2}")
    except Exception as e:
        print(f"  [WARN] Δ-цвета: {e}")


def sync_result(sh, con):
    print("\\n[Лист РЕЗУЛЬТАТ]")
    ws = get_or_create_sheet(sh, "РЕЗУЛЬТАТ")
    data = build_result(con)
    clear_and_write(ws, data)
    print(f"  Записано строк: {len(data)}")
    format_result(ws)

'''

# Вставляем перед def build_money
anchor = "def build_money(con):"
if "def format_money" not in src:
    src = src.replace(anchor, format_money_code + "\n\n" + anchor, 1)
    print("[OK] format_money + format_result добавлены")
else:
    print("[i] Уже есть")

# Заменяем main loop
old_main = '''    # Остальные листы — без форматирования
    for name, fn in [("ДЕНЬГИ", build_money), ("РЕЗУЛЬТАТ", build_result)]:
        print(f"\\n[Лист {name}]")
        ws = get_or_create_sheet(sh, name)
        data = fn(con)
        clear_and_write(ws, data)
        print(f"  Записано строк: {len(data)}")'''

new_main = '''    # ДЕНЬГИ и РЕЗУЛЬТАТ — с форматированием
    sync_money(sh, con)
    sync_result(sh, con)'''

if old_main in src:
    src = src.replace(old_main, new_main)
    print("[OK] main обновлён")
else:
    print("[?] Не нашёл main loop")

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("\nГотово. Запускай: py sheets_sync.py")
