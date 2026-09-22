"""
patch_actions_notes_fix.py — перемещает примечания на названия категорий,
добавляет короткое описание в колонку E сводки.
"""
src = open("sheets_sync.py", encoding="utf-8").read()

# === 1. build_actions — добавляем колонку "Что значит" в сводку ===
old = '''    # Сводка — пустая A, данные в B/C/D
    data.append(["", "Категория", "SKU", "Эффект ₽/мес"])
    for cat in ["УБЫТОЧНЫЙ", "ДОСТАВКА", "КАРТОЧКА", "КРИТ. МАРЖА", "МАСШТАБ"]:
        if cat in cats:
            grp_effect = sum(g["effect"] for g in cats[cat])
            data.append(["", cat, len(cats[cat]), f"{grp_effect:,.0f}"])
    data.append([])'''

new = '''    # Сводка — A пусто, B/C/D/E — данные
    cat_short = {
        "УБЫТОЧНЫЙ":   "Каждый заказ в убыток → поднять цену или снять",
        "ДОСТАВКА":    "Корзины есть, заказов нет → проверить доставку",
        "КАРТОЧКА":    "Заходы есть, заказов нет → фото/описание",
        "КРИТ. МАРЖА": "Маржа 0-5% → поднять цену",
        "МАСШТАБ":     "Маржа 25%+ → в акции, пополнить остатки",
    }
    data.append(["", "Категория", "SKU", "Эффект ₽/мес", "Что значит"])
    for cat in ["УБЫТОЧНЫЙ", "ДОСТАВКА", "КАРТОЧКА", "КРИТ. МАРЖА", "МАСШТАБ"]:
        if cat in cats:
            grp_effect = sum(g["effect"] for g in cats[cat])
            data.append(["", cat, len(cats[cat]), f"{grp_effect:,.0f}", cat_short.get(cat, "")])
    data.append([])'''

if old in src:
    src = src.replace(old, new)
    print("[OK] build_actions — добавлена колонка 'Что значит'")
else:
    print("[?] Не нашёл сводку в build_actions")

# === 2. format_actions — примечания на B4:B8 + формат E4:E8 ===
old_notes = '''    # === Примечания к категориям (E5-E9) ===
    cat_notes = {
        "УБЫТОЧНЫЙ":   "Маржа отрицательная. Каждый заказ приносит убыток. Действие: поднять цену или снять.",
        "ДОСТАВКА":    "Клиенты дошли до корзины, но не оформили. Обычно — проблема доставки: габариты, сроки, ПВЗ.",
        "КАРТОЧКА":    "Показы и заходы есть, заказов нет. Проблема в карточке: фото, описание, отзывы.",
        "КРИТ. МАРЖА": "Маржа 0-5%. Работает почти в ноль. Действие: поднять цену.",
        "МАСШТАБ":     "Маржа 25%+. Хорошо идёт. Действие: в акции, пополнить остатки.",
    }
    note_row = 4
    for cat in order:
        if cat in cats:
            ops.append({"type": "note", "cell": f"E{note_row}",
                        "note": cat_notes.get(cat, "")})
            note_row += 1

    # Другие примечания
    ops.append({"type": "note", "cell": "B3",
                "note": "Наведи на E4-E8 — что означает каждая категория."})
    ops.append({"type": "note", "cell": f"F{table_hdr}",
                "note": "Суммарный эффект категории в ₽/мес, если выполнить все действия."})
    ops.append({"type": "note", "cell": f"G{table_hdr}",
                "note": "Напиши \'да\' в строке — py run.py подхватит и добавит в дневник решений."})'''

new_notes = '''    # === Примечания на НАЗВАНИЯ категорий (B4:B8) ===
    cat_notes = {
        "УБЫТОЧНЫЙ":   "Маржа отрицательная. Каждый заказ приносит убыток. Что делать: поднять цену или снять с продажи. См. лист ДЕЛАЙ для конкретных SKU.",
        "ДОСТАВКА":    "Клиенты дошли до корзины, но не оформили заказ. Обычно — проблема доставки: габариты, сроки, ПВЗ. Проверить в ЛК Ozon брошенные корзины.",
        "КАРТОЧКА":    "Показы и заходы есть, но заказов нет. Проблема в карточке: главное фото, описание, отзывы. Переделать карточку.",
        "КРИТ. МАРЖА": "Маржа 0-5%. Работает почти в ноль. Что делать: поднять цену на 5-10%.",
        "МАСШТАБ":     "Маржа 25%+. Товар хорошо идёт. Что делать: включить в акции, бустинг, пополнить остатки.",
    }
    note_row = 4
    for cat in order:
        if cat in cats:
            # Примечание на название категории (B4:B8)
            ops.append({"type": "note", "cell": f"B{note_row}",
                        "note": cat_notes.get(cat, "")})
            note_row += 1

    # Заголовок "Что значит" — шире
    ops.append({"type": "format", "range": "E3",
                "format": CellFormat(
                    backgroundColor=Color(0.95, 0.95, 0.95),
                    textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=COLHDR_FG),
                    horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
                )})
    # Строки 4-8 в колонке E — обычный текст
    for r in range(4, 9):
        ops.append({"type": "format", "range": f"E{r}",
                    "format": CellFormat(
                        textFormat=TextFormat(fontSize=9, italic=True, foregroundColor=MUTED_FG),
                        horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
                        wrapStrategy='WRAP',
                    )})

    # Заголовок B3:E3 объединяем для центрирования
    ops.append({"type": "merge", "range": "B3:E3"})

    # Другие примечания
    ops.append({"type": "note", "cell": "B3",
                "note": "Наведи на название категории (B4:B8) — подробное описание. Колонка E — краткая расшифровка."})
    ops.append({"type": "note", "cell": f"F{table_hdr}",
                "note": "Суммарный эффект категории в ₽/мес, если выполнить все действия."})
    ops.append({"type": "note", "cell": f"G{table_hdr}",
                "note": "Напиши \'да\' в строке — py run.py подхватит и добавит в дневник решений."})'''

if old_notes in src:
    src = src.replace(old_notes, new_notes)
    print("[OK] примечания перенесены на B4:B8, добавлена колонка E")
else:
    print("[?] Не нашёл блок примечаний")

# === 3. Ширина E в сводке — 400 (не мешает таблице действий) ===
# Ширина E уже 400 для таблицы, оставляем

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("\nГотово. Запускай: py sheets_sync.py")
