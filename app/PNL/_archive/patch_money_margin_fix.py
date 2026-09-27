"""
patch_money_margin_fix.py — маржа в % и цветной фон.
"""
src = open("sheets_sync.py", encoding="utf-8").read()

# 1. build_money — маржа как процент
src = src.replace(
    'f"{profit:,.0f}", f"{margin:.3f}", orders, f"{avg:,.0f}",',
    'f"{profit:,.0f}", f"{margin*100:.1f}%", orders, f"{avg:,.0f}",'
)
print("[OK] маржа как % в build_money")

# 2. format_money — убираем блок с условным форматированием, добавляем ручное
old = '''    # Условное форматирование маржи — отдельным запросом через conditional_format
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
        print(f"  [WARN] Условное форматирование маржи не применилось: {e}")'''

new = '''    # Ручное цветное форматирование маржи (G5:G7) по значениям
    try:
        vals = ws.get("G5:G7")
        ops2 = []
        for i, row in enumerate(vals):
            if not row:
                continue
            v = row[0].strip().rstrip("%")
            try:
                m = float(v)  # уже в %
            except ValueError:
                continue
            r = 5 + i
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
            print(f"  Цвет маржи применён: {n2}")
    except Exception as e:
        print(f"  [WARN] Цвет маржи: {e}")'''

if old in src:
    src = src.replace(old, new)
    print("[OK] условное форматирование заменено на ручное")
else:
    print("[?] Не нашёл блок условного форматирования")

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("\nГотово. Запускай: py sheets_sync.py")
