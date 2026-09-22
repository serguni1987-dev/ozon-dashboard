"""
patch_prices_verdicts.py — добавляет блок ВЫВОДЫ внизу листа ЦЕНЫ.
"""
src = open("sheets_sync.py", encoding="utf-8").read()

# ============ 1. В build_prices — добавляем выводы после таблицы ============
old_return = '''        data.append([
            it["offer_id"],
            it["name"],
            f"{it['cost']:,.0f}",
            f"{it['price']:,.0f}",
            f"{it['min_price']:,.0f}" if it["min_price"] else "—",
            it["color"],
            profit_str,
            orders,
            f"{it['rev_30d']:,.0f}" if it["rev_30d"] else "—",
            stock,
            verdict,
        ])

    return data, items'''

new_return = '''        data.append([
            it["offer_id"],
            it["name"],
            f"{it['cost']:,.0f}",
            f"{it['price']:,.0f}",
            f"{it['min_price']:,.0f}" if it["min_price"] else "—",
            it["color"],
            profit_str,
            orders,
            f"{it['rev_30d']:,.0f}" if it["rev_30d"] else "—",
            stock,
            verdict,
        ])

    # === Собираем статистику для выводов ===
    red_total = sum(1 for i in items if i["color"] == "RED")
    red_with_stock = sum(1 for i in items if i["color"] == "RED" and i["stock"] > 0)
    red_no_stock = red_total - red_with_stock
    loss_with_stock = sum(1 for i in items if i["unit_profit"] < 0 and i["stock"] > 0)
    loss_no_stock = sum(1 for i in items if i["unit_profit"] < 0 and i["stock"] == 0)
    yellow_no_stock = sum(1 for i in items if i["color"] == "YELLOW" and i["stock"] == 0)
    super_total = sum(1 for i in items if i["color"] == "SUPER")
    super_with_stock = sum(1 for i in items if i["color"] == "SUPER" and i["stock"] > 0)
    active_red = sum(1 for i in items if i["color"] == "RED" and i["orders_30d"] > 0)

    total_stock_sku = sum(1 for i in items if i["stock"] > 0)

    # === ВЫВОДЫ ===
    data.append(["", "", "", "", "", "", "", "", "", "", ""])
    data.append(["ВЫВОДЫ", "", "", "", "", "", "", "", "", "", ""])

    # 1. Общая оценка ассортимента
    if red_total > 100:
        v1 = f"❌ {red_total} SKU в RED (дорого рынку) — но {red_no_stock} из них без остатка, это не проблема цены"
    elif red_total > 30:
        v1 = f"⚠ {red_total} SKU в RED — стоит проверить цены"
    else:
        v1 = f"✅ Мало RED SKU ({red_total}) — цены в норме"

    # 2. Что реально можно чинить
    if red_with_stock > 0 or loss_with_stock > 0:
        real_problems = red_with_stock + loss_with_stock
        v2 = (f"→ Реальных проблем цены: {real_problems} SKU  "
              f"(RED с остатком: {red_with_stock}, убыточных с остатком: {loss_with_stock})  "
              f"— работать с ними через apply_prices.py")
    else:
        v2 = "→ Реальных проблем цены нет — все RED/убыточные без остатка"

    # 3. Что снять или заказать
    no_stock = red_no_stock + yellow_no_stock + loss_no_stock
    if no_stock > 50:
        v3 = (f"📦 {no_stock} SKU закончились (нет остатка) — "
              f"решить: заказать или архивировать")
    elif no_stock > 0:
        v3 = f"📦 {no_stock} SKU закончились — проверить, нужны ли"
    else:
        v3 = "✅ Все SKU с остатком"

    # 4. SUPER — можно поднять цену
    if super_with_stock > 0:
        v4 = (f"💰 {super_with_stock} SKU в SUPER (дешевле рынка) с остатком — "
              f"можно поднять цену без потери продаж")
    elif super_total > 0:
        v4 = f"ℹ {super_total} SKU в SUPER — все без остатка"
    else:
        v4 = "ℹ Нет SKU в SUPER"

    # 5. Активные RED — конкуренция
    if active_red > 0:
        v5 = (f"🔥 {active_red} SKU в RED, но всё равно продаются — "
              f"клиенты готовы платить дороже рынка, можно поднять цену")
    else:
        v5 = ""

    # 6. Итог
    if red_with_stock + loss_with_stock == 0:
        v6 = "→ ИТОГ: с ценами работать не нужно — проблема в ассортименте и остатках"
    elif red_with_stock + loss_with_stock < 10:
        v6 = "→ ИТОГ: точечно поправить цены у 1–10 SKU через apply_prices.py"
    else:
        v6 = "→ ИТОГ: массовая коррекция цен через apply_prices.py даст эффект"

    data.append([v1, "", "", "", "", "", "", "", "", "", ""])
    data.append([v2, "", "", "", "", "", "", "", "", "", ""])
    data.append([v3, "", "", "", "", "", "", "", "", "", ""])
    data.append([v4, "", "", "", "", "", "", "", "", "", ""])
    if v5:
        data.append([v5, "", "", "", "", "", "", "", "", "", ""])
    data.append([v6, "", "", "", "", "", "", "", "", "", ""])

    # Возвращаем число выводов, чтобы знать, где они на листе
    n_verdicts = 6 + (1 if v5 else 0)
    return data, items, n_verdicts'''

if old_return in src:
    src = src.replace(old_return, new_return)
    print("[OK] build_prices: добавлены выводы")
else:
    print("[?] Не нашёл блок return в build_prices")

# ============ 2. format_prices — принимает n_verdicts и форматирует выводы ============
src = src.replace(
    "def format_prices(ws, items):",
    "def format_prices(ws, items, n_verdicts=6):"
)
print("[OK] format_prices: добавлен параметр n_verdicts")

# В конце format_prices — форматируем выводы
old_end = '''    # Примечания
    ops.append({"type": "note", "cell": "F5",
                "note": "Индекс цены Ozon (color_index): RED — дорого рынку, YELLOW — средне, GREEN — хорошо, SUPER — самый дешёвый, WITHOUT_INDEX — Ozon не сравнивает."})
    ops.append({"type": "note", "cell": "G5",
                "note": "Прибыль на единицу = Цена × (1 − комиссия 2,81% − услуги 14,2%) − себестоимость."})
    ops.append({"type": "note", "cell": "H5",
                "note": "❌ Убыток / ⚠ Тонко / ✅ Норма / 🟢 Отлично."})

    n = batch_apply(ws, sid, ops)
    print(f"  Отправлено форматирований одним batch: {n}")'''

new_end = '''    # Примечания
    ops.append({"type": "note", "cell": "F5",
                "note": "Индекс цены Ozon (color_index): RED — дорого рынку, YELLOW — средне, GREEN — хорошо, SUPER — самый дешёвый, WITHOUT_INDEX — Ozon не сравнивает."})
    ops.append({"type": "note", "cell": "G5",
                "note": "Прибыль на единицу = Цена × (1 − комиссия 2,81% − услуги 14,2%) − себестоимость."})
    ops.append({"type": "note", "cell": "J5",
                "note": "Остаток актуальный из Ozon API. 0 — нет товара, 1-2 — мало, 3+ — достаточно."})

    # === ВЫВОДЫ внизу ===
    verdicts_start = table_start + len(items) + 2  # +1 пустая, +1 заголовок
    ops.append({"type": "merge", "range": f"A{verdicts_start}:K{verdicts_start}"})
    ops.append({"type": "format", "range": f"A{verdicts_start}:K{verdicts_start}",
                "format": FMT_SUBHEADER})
    ops.append({"type": "row_height", "row": verdicts_start, "height": 26})

    for i in range(n_verdicts):
        r = verdicts_start + 1 + i
        ops.append({"type": "merge", "range": f"A{r}:K{r}"})
        ops.append({"type": "row_height", "row": r, "height": 30})

    n = batch_apply(ws, sid, ops)
    print(f"  Отправлено форматирований одним batch: {n}")

    # Цвет выводов
    try:
        vals = ws.get(f"A{verdicts_start + 1}:A{verdicts_start + n_verdicts}")
        ops2 = []
        for i, row in enumerate(vals):
            if not row:
                continue
            v = row[0]
            r = verdicts_start + 1 + i
            if v.startswith("❌") or v.startswith("⚠"):
                bg, fg = BAD_BG, BAD_FG
            elif v.startswith("✅") or v.startswith("🟢"):
                bg, fg = GOOD_BG, GOOD_FG
            elif v.startswith("→ ИТОГ"):
                bg, fg = Color(0.90, 0.94, 1.0), Color(0.10, 0.20, 0.50)
            elif v.startswith("→"):
                bg, fg = INFO_BG, Color(0.10, 0.20, 0.50)
            elif v.startswith("💰"):
                bg, fg = Color(0.95, 0.95, 0.75), Color(0.5, 0.4, 0)
            else:
                bg, fg = SUBHEADER_BG, Color(0.2, 0.2, 0.2)
            ops2.append({"type": "format", "range": f"A{r}:K{r}", "format": CellFormat(
                backgroundColor=bg,
                textFormat=TextFormat(fontSize=11, foregroundColor=fg),
                horizontalAlignment='LEFT', verticalAlignment='MIDDLE', wrapStrategy='WRAP',
            )})
        if ops2:
            n2 = batch_apply(ws, sid, ops2)
            print(f"  Цвет выводов: {n2}")
    except Exception as e:
        print(f"  [WARN] Цвет выводов: {e}")'''

if old_end in src:
    src = src.replace(old_end, new_end)
    print("[OK] format_prices: добавлено форматирование выводов")

# ============ 3. sync_prices — принимать n_verdicts ============
old_sync = '''def sync_prices(sh, con):
    print("\\n[Лист ЦЕНЫ]")
    ws = get_or_create_sheet(sh, "ЦЕНЫ")
    data, items = build_prices(con)
    clear_and_write(ws, data)
    print(f"  Записано строк: {len(data)}")
    format_prices(ws, items)'''

new_sync = '''def sync_prices(sh, con):
    print("\\n[Лист ЦЕНЫ]")
    ws = get_or_create_sheet(sh, "ЦЕНЫ")
    data, items, n_verdicts = build_prices(con)
    clear_and_write(ws, data)
    print(f"  Записано строк: {len(data)}")
    format_prices(ws, items, n_verdicts)'''

if old_sync in src:
    src = src.replace(old_sync, new_sync)
    print("[OK] sync_prices: передаёт n_verdicts")

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("\nГотово. Запускай: py sheets_sync.py")
