"""
patch_actions_format.py — добавляет форматирование для листа ДЕЛАЙ.
"""
src = open("sheets_sync.py", encoding="utf-8").read()

# === 1. Добавляем цвета для категорий ===
colors_block = '''
# Цвета категорий (фон / текст)
CAT_COLORS = {
    "УБЫТОЧНЫЙ":  (Color(0xF4/255, 0xCC/255, 0xCC/255), Color(0.55, 0.05, 0.05)),  # красный
    "ДОСТАВКА":   (Color(0xFF/255, 0xF2/255, 0xCC/255), Color(0.60, 0.45, 0.00)),  # жёлтый
    "КАРТОЧКА":   (Color(0xFD/255, 0xE9/255, 0xD0/255), Color(0.55, 0.35, 0.05)),  # светло-оранжевый
    "КРИТ. МАРЖА":(Color(0xFC/255, 0xE5/255, 0xCD/255), Color(0.60, 0.30, 0.00)),  # оранжевый
    "МАСШТАБ":    (Color(0xD9/255, 0xEA/255, 0xD3/255), Color(0.10, 0.40, 0.10)),  # зелёный
}

'''
if "CAT_COLORS" not in src:
    # Вставим после определения FMT_ACTION_ITEM
    anchor = '''FMT_ACTION_ITEM = CellFormat(
    textFormat=TextFormat(fontSize=11),
    horizontalAlignment='LEFT', wrapStrategy='WRAP',
)'''
    src = src.replace(anchor, anchor + "\n" + colors_block)
    print("[OK] CAT_COLORS добавлены")
else:
    print("[i] CAT_COLORS уже есть")


# === 2. Функция format_actions + sync_actions ===
format_actions_code = '''

# ============ ЛИСТ ДЕЛАЙ ============
def format_actions(ws, actions, total_effect):
    sid = ws.id
    ops = []

    # Сброс старых merge
    ops.append({"type": "unmerge", "range": "A1:Z200"})

    # === Заголовок A1:G1 ===
    ops.append({"type": "merge", "range": "A1:G1"})
    ops.append({"type": "format", "range": "A1:G1", "format": FMT_TITLE})

    # === Подзаголовок A2:G2 — итог ===
    subtitle_fmt = CellFormat(
        textFormat=TextFormat(bold=True, fontSize=12, foregroundColor=Color(0.15, 0.15, 0.15)),
        backgroundColor=SUBHEADER_BG,
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "merge", "range": "A2:G2"})
    ops.append({"type": "format", "range": "A2:G2", "format": subtitle_fmt})

    # === Пустая строка 3, потом сводка по категориям ===
    # Строки 4-8: Категория | SKU | Эффект
    cats = {}
    for a in actions:
        cats.setdefault(a["category"], []).append(a)

    order = ["УБЫТОЧНЫЙ", "ДОСТАВКА", "КАРТОЧКА", "КРИТ. МАРЖА", "МАСШТАБ"]

    # Заголовок сводки (строка 4)
    hdr = CellFormat(
        textFormat=TextFormat(bold=True, fontSize=10, foregroundColor=COLHDR_FG),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "format", "range": "A4:C4", "format": hdr})

    # Строки 5-9: категории с цветами
    row = 5
    for cat in order:
        if cat not in cats:
            continue
        bg, fg = CAT_COLORS.get(cat, (SUBHEADER_BG, Color(0,0,0)))
        fmt_cat = CellFormat(
            backgroundColor=bg,
            textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=fg),
            horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
        )
        ops.append({"type": "format", "range": f"A{row}:C{row}", "format": fmt_cat})
        ops.append({"type": "row_height", "row": row, "height": 28})
        row += 1

    # === Таблица действий начинается после пустой строки ===
    table_start = row + 1  # +1 для пустой

    # Заголовки таблицы
    tbl_hdr = CellFormat(
        backgroundColor=HEADER_BG,
        textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=HEADER_FG),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "format",
                "range": f"A{table_start}:G{table_start}",
                "format": tbl_hdr})
    ops.append({"type": "row_height", "row": table_start, "height": 36})

    # Данные таблицы
    body_center = CellFormat(
        textFormat=TextFormat(fontSize=10),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    body_left = CellFormat(
        textFormat=TextFormat(fontSize=10),
        horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
        wrapStrategy='CLIP',
    )
    body_left_wrap = CellFormat(
        textFormat=TextFormat(fontSize=10),
        horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
        wrapStrategy='WRAP',
    )
    body_effect = CellFormat(
        textFormat=TextFormat(fontSize=11, bold=True),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    body_offer = CellFormat(
        textFormat=TextFormat(fontSize=10, bold=True),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    done_cell = CellFormat(
        textFormat=TextFormat(fontSize=10),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
        backgroundColor=Color(0.97, 0.97, 0.97),
    )

    data_row = table_start + 1
    for i, a in enumerate(actions):
        cat = a["category"]
        bg, fg = CAT_COLORS.get(cat, (SUBHEADER_BG, Color(0,0,0)))

        # Категория — цветной текст на белом фоне
        cat_cell = CellFormat(
            textFormat=TextFormat(fontSize=10, bold=True, foregroundColor=fg),
            horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
        )

        ops.append({"type": "format", "range": f"A{data_row}", "format": body_center})
        ops.append({"type": "format", "range": f"B{data_row}", "format": cat_cell})
        ops.append({"type": "format", "range": f"C{data_row}", "format": body_offer})
        ops.append({"type": "format", "range": f"D{data_row}", "format": body_left})
        ops.append({"type": "format", "range": f"E{data_row}", "format": body_left_wrap})
        ops.append({"type": "format", "range": f"F{data_row}", "format": body_effect})
        ops.append({"type": "format", "range": f"G{data_row}", "format": done_cell})
        ops.append({"type": "row_height", "row": data_row, "height": 30})
        data_row += 1

    # === Ширины колонок ===
    ops.append({"type": "width", "col": "A", "width": 50})    # #
    ops.append({"type": "width", "col": "B", "width": 140})   # Категория
    ops.append({"type": "width", "col": "C", "width": 140})   # Offer ID
    ops.append({"type": "width", "col": "D", "width": 320})   # Название
    ops.append({"type": "width", "col": "E", "width": 380})   # Что делать
    ops.append({"type": "width", "col": "F", "width": 140})   # Эффект
    ops.append({"type": "width", "col": "G", "width": 110})   # Сделано?

    # === Заморозка ===
    ops.append({"type": "frozen", "rows": table_start})

    # === Примечания ===
    ops.append({"type": "note", "cell": "B4",
                "note": "Категории отсортированы по важности: сначала убытки, потом доставка, карточки, цены, масштаб."})
    ops.append({"type": "note", "cell": "F4",
                "note": "Суммарный эффект каждой категории в ₽/мес, если выполнить все действия."})
    ops.append({"type": "note", "cell": f"G{table_start}",
                "note": "Напиши 'да' в строке действия — на следующее утро py run.py подхватит и добавит в дневник решений."})

    n = batch_apply(ws, sid, ops)
    print(f"  Отправлено форматирований одним batch: {n}")


def sync_actions(sh, con):
    print("\\n[Лист ДЕЛАЙ]")
    ws = get_or_create_sheet(sh, "ДЕЛАЙ")
    data = build_actions(con)
    clear_and_write(ws, data)
    print(f"  Записано строк: {len(data)}")

    # Достаём actions для форматирования
    from plan_core import get_actions
    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    month_ago = (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")
    actions = get_actions(con, month_ago, max_date)
    total_effect = sum(a["effect"] for a in actions)

    format_actions(ws, actions, total_effect)
    print("  Форматирование применено")
'''

# Вставляем перед "def build_money"
anchor2 = "def build_money(con):"
if "def format_actions" not in src:
    src = src.replace(anchor2, format_actions_code + "\n\n" + anchor2)
    print("[OK] format_actions + sync_actions добавлены")
else:
    print("[i] format_actions уже есть")

# === 3. Заменяем вызов в main для ДЕЛАЙ ===
old_main = '''    for name, fn in [("ДЕЛАЙ", build_actions), ("ДЕНЬГИ", build_money), ("РЕЗУЛЬТАТ", build_result)]:
        print(f"\\n[Лист {name}]")
        ws = get_or_create_sheet(sh, name)
        data = fn(con)
        clear_and_write(ws, data)
        print(f"  Записано строк: {len(data)}")'''

new_main = '''    # Лист ДЕЛАЙ — со своим форматированием
    sync_actions(sh, con)

    # Остальные листы — без форматирования
    for name, fn in [("ДЕНЬГИ", build_money), ("РЕЗУЛЬТАТ", build_result)]:
        print(f"\\n[Лист {name}]")
        ws = get_or_create_sheet(sh, name)
        data = fn(con)
        clear_and_write(ws, data)
        print(f"  Записано строк: {len(data)}")'''

if old_main in src:
    src = src.replace(old_main, new_main)
    print("[OK] main обновлён — ДЕЛАЙ через sync_actions")
else:
    print("[?] Не нашёл main loop")

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("\nГотово. Запускай: py sheets_sync.py")
