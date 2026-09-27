"""
patch_actions_fix_rows.py — переписывает format_actions с точными строками.
Структура листа ДЕЛАЙ (1-indexed):
  1: ПЛАН ДЕЙСТВИЙ
  2: подзаголовок (итог)
  3: пусто
  4: Категория | SKU | Эффект ₽/мес   ← заголовок сводки
  5-9: категории
  10: пусто
  11: # | Категория | ... ← заголовки таблицы действий
  12+: действия
"""
import re

src = open("sheets_sync.py", encoding="utf-8").read()

# Находим format_actions целиком
pattern = re.compile(
    r"def format_actions\(ws, actions, total_effect\):.*?(?=\ndef sync_actions)",
    re.DOTALL
)

new_func = '''def format_actions(ws, actions, total_effect):
    sid = ws.id
    ops = []

    # Сброс старых merge + фильтра
    ops.append({"type": "unmerge", "range": "A1:Z200"})
    # Сброс старого фильтра (если был)
    try:
        ws.spreadsheet.batch_update({"requests": [{
            "clearBasicFilter": {"sheetId": sid}
        }]})
    except Exception:
        pass

    # === Заголовок A1:G1 ===
    ops.append({"type": "merge", "range": "A1:G1"})
    ops.append({"type": "format", "range": "A1:G1", "format": FMT_TITLE})
    ops.append({"type": "row_height", "row": 1, "height": 40})

    # === Подзаголовок A2:G2 ===
    subtitle_fmt = CellFormat(
        textFormat=TextFormat(bold=True, fontSize=12, foregroundColor=Color(0.15, 0.15, 0.15)),
        backgroundColor=SUBHEADER_BG,
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "merge", "range": "A2:G2"})
    ops.append({"type": "format", "range": "A2:G2", "format": subtitle_fmt})
    ops.append({"type": "row_height", "row": 2, "height": 30})

    # === Сводка: заголовок в строке 4, категории в 5-9 ===
    hdr = CellFormat(
        backgroundColor=Color(0.95, 0.95, 0.95),
        textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=COLHDR_FG),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "format", "range": "B4:D4", "format": hdr})
    ops.append({"type": "row_height", "row": 4, "height": 28})

    order = ["УБЫТОЧНЫЙ", "ДОСТАВКА", "КАРТОЧКА", "КРИТ. МАРЖА", "МАСШТАБ"]
    cats = {}
    for a in actions:
        cats.setdefault(a["category"], []).append(a)

    # Строки 5-9 — категории
    row_num = 5
    for cat in order:
        if cat not in cats:
            continue
        bg, fg = CAT_COLORS.get(cat, (SUBHEADER_BG, Color(0,0,0)))
        fmt_cat_name = CellFormat(
            backgroundColor=bg,
            textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=fg),
            horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
        )
        fmt_cat_num = CellFormat(
            backgroundColor=bg,
            textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=fg),
            horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
        )
        ops.append({"type": "format", "range": f"B{row_num}", "format": fmt_cat_name})
        ops.append({"type": "format", "range": f"C{row_num}", "format": fmt_cat_num})
        ops.append({"type": "format", "range": f"D{row_num}", "format": fmt_cat_num})
        ops.append({"type": "row_height", "row": row_num, "height": 28})
        row_num += 1

    # === Таблица действий: заголовки в строке 11 ===
    table_hdr = 11
    last_row = table_hdr + len(actions)

    tbl_hdr = CellFormat(
        backgroundColor=HEADER_BG,
        textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=HEADER_FG),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "format", "range": f"A{table_hdr}:G{table_hdr}", "format": tbl_hdr})
    ops.append({"type": "row_height", "row": table_hdr, "height": 36})

    # Данные таблицы
    body_center = CellFormat(
        textFormat=TextFormat(fontSize=10),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    body_left = CellFormat(
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

    r = table_hdr + 1
    for a in actions:
        cat = a["category"]
        _, fg = CAT_COLORS.get(cat, (SUBHEADER_BG, Color(0,0,0)))
        cat_cell = CellFormat(
            textFormat=TextFormat(fontSize=10, bold=True, foregroundColor=fg),
            horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
        )
        ops.append({"type": "format", "range": f"A{r}", "format": body_center})
        ops.append({"type": "format", "range": f"B{r}", "format": cat_cell})
        ops.append({"type": "format", "range": f"C{r}", "format": body_offer})
        ops.append({"type": "format", "range": f"D{r}", "format": body_left})
        ops.append({"type": "format", "range": f"E{r}", "format": body_left})
        ops.append({"type": "format", "range": f"F{r}", "format": body_effect})
        ops.append({"type": "format", "range": f"G{r}", "format": done_cell})
        ops.append({"type": "row_height", "row": r, "height": 60})
        r += 1

    # === Ширины колонок ===
    ops.append({"type": "width", "col": "A", "width": 60})
    ops.append({"type": "width", "col": "B", "width": 180})
    ops.append({"type": "width", "col": "C", "width": 170})
    ops.append({"type": "width", "col": "D", "width": 380})
    ops.append({"type": "width", "col": "E", "width": 400})
    ops.append({"type": "width", "col": "F", "width": 140})
    ops.append({"type": "width", "col": "G", "width": 120})

    # === Заморозка ===
    ops.append({"type": "frozen", "rows": table_hdr})

    # === ФИЛЬТР на таблицу действий ===
    ops.append({"type": "filter", "range": f"A{table_hdr}:G{last_row}"})

    # === Примечания к категориям (E5-E9) ===
    cat_notes = {
        "УБЫТОЧНЫЙ":   "Маржа отрицательная. Каждый заказ приносит убыток. Действие: поднять цену или снять.",
        "ДОСТАВКА":    "Клиенты дошли до корзины, но не оформили. Обычно — проблема доставки: габариты, сроки, ПВЗ.",
        "КАРТОЧКА":    "Показы и заходы есть, заказов нет. Проблема в карточке: фото, описание, отзывы.",
        "КРИТ. МАРЖА": "Маржа 0-5%. Работает почти в ноль. Действие: поднять цену.",
        "МАСШТАБ":     "Маржа 25%+. Хорошо идёт. Действие: в акции, пополнить остатки.",
    }
    note_row = 5
    for cat in order:
        if cat in cats:
            ops.append({"type": "note", "cell": f"E{note_row}",
                        "note": cat_notes.get(cat, "")})
            note_row += 1

    # Другие примечания
    ops.append({"type": "note", "cell": "B4",
                "note": "Наведи на E5-E9 — что означает каждая категория."})
    ops.append({"type": "note", "cell": f"F{table_hdr}",
                "note": "Суммарный эффект категории в ₽/мес, если выполнить все действия."})
    ops.append({"type": "note", "cell": f"G{table_hdr}",
                "note": "Напиши \'да\' в строке — py run.py подхватит и добавит в дневник решений."})

    n = batch_apply(ws, sid, ops)
    print(f"  Отправлено форматирований одним batch: {n}")

'''

src, n = pattern.subn(new_func, src)

if n == 0:
    print("[FAIL] Не нашёл format_actions")
    exit(1)

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("[OK] format_actions переписана")
print("Запускай: py sheets_sync.py")
