"""
patch_actions_filter_notes.py — фильтр + примечания к категориям.
"""
src = open("sheets_sync.py", encoding="utf-8").read()

# === 1. Добавляем тип "filter" в batch_apply ===
old = '''        elif t == "row_height":'''
new = '''        elif t == "filter":
            requests.append({
                "setBasicFilter": {
                    "filter": {
                        "range": _a1_to_grid_range(op["range"], sheet_id)
                    }
                }
            })
        elif t == "row_height":'''

if old in src and "setBasicFilter" not in src:
    src = src.replace(old, new, 1)
    print("[OK] тип 'filter' добавлен в batch_apply")
else:
    print("[i] filter уже есть или не нашёл место")

# === 2. В format_actions добавляем фильтр + примечания ===
old_notes = '''    # === Примечания ===
    ops.append({"type": "note", "cell": "B4",
                "note": "Категории отсортированы по важности: сначала убытки, потом доставка, карточки, цены, масштаб."})
    ops.append({"type": "note", "cell": "F4",
                "note": "Суммарный эффект каждой категории в ₽/мес, если выполнить все действия."})
    ops.append({"type": "note", "cell": f"G{table_start}",
                "note": "Напиши \'да\' в строке действия — на следующее утро py run.py подхватит и добавит в дневник решений."})'''

new_notes = '''    # === Фильтр на таблицу действий ===
    last_row = table_start + len(actions)
    ops.append({"type": "filter", "range": f"A{table_start}:G{last_row}"})

    # === Примечания: объяснение категорий (E4-E8) ===
    cat_notes = {
        "УБЫТОЧНЫЙ":   "Маржа отрицательная. Каждый заказ приносит убыток. Действие: поднять цену или снять с продажи.",
        "ДОСТАВКА":    "Клиенты дошли до корзины, но не оформили. Обычно — проблема доставки: габариты, сроки, ПВЗ в регионе.",
        "КАРТОЧКА":    "Показы и заходы есть, заказов нет. Проблема в карточке: фото, описание, отзывы.",
        "КРИТ. МАРЖА": "Маржа 0–5%. Работает почти в ноль. Действие: поднять цену.",
        "МАСШТАБ":     "Маржа ≥25%. Хорошо идёт. Действие: включить в акции, бумпнуть остатки.",
    }
    # Примечания ставим в столбец E — рядом с каждой категорией
    for r_off, cat in enumerate(order):
        if cat in cats:
            r = 5 + r_off  # совпадает с циклом выше
            ops.append({"type": "note", "cell": f"E{r}",
                        "note": cat_notes.get(cat, "")})

    # === Другие примечания ===
    ops.append({"type": "note", "cell": "B4",
                "note": "Категории отсортированы по важности: сначала убытки, потом доставка, карточки, цены, масштаб. Наведи на E5–E9 — что означает каждая."})
    ops.append({"type": "note", "cell": f"F{table_start}",
                "note": "Суммарный эффект категории в ₽/мес, если выполнить все действия."})
    ops.append({"type": "note", "cell": f"G{table_start}",
                "note": "Напиши \'да\' в строке — на следующее утро py run.py подхватит и добавит в дневник решений."})'''

if old_notes in src:
    src = src.replace(old_notes, new_notes)
    print("[OK] фильтр + примечания к категориям добавлены")
else:
    print("[?] Не нашёл блок примечаний")

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("\nГотово. Запускай: py sheets_sync.py")
