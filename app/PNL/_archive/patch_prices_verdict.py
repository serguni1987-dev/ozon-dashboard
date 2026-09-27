"""
patch_prices_verdict.py — добавляет колонки Заказов 30д, Выручка 30д,
и умную оценку (маржа + продажи).
"""
import re

src = open("sheets_sync.py", encoding="utf-8").read()

# ============ 1. В build_prices ============
# Обновляем подзаголовок: добавить "не продаются: X"
old_sub = '''    # Сводка
    from collections import Counter
    colors = Counter(i["color"] for i in items)
    total = len(items)
    red_count = colors.get("RED", 0)
    loss_count = sum(1 for i in items if i["unit_profit"] < 0)

    data = [
        ["ЦЕНЫ — актуальные из Ozon API", "", "", "", "", "", "", ""],
        [f"всего SKU: {total}  |  🔴 RED (дорого рынку): {red_count}  |  "
         f"убыточных на единицу: {loss_count}  |  обновлено {datetime.now().strftime('%H:%M')}",
         "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", ""],
    ]'''

new_sub = '''    # Сводка
    from collections import Counter
    colors = Counter(i["color"] for i in items)
    total = len(items)
    red_count = colors.get("RED", 0)
    loss_count = sum(1 for i in items if i["unit_profit"] < 0)
    dead_red = sum(1 for i in items if i["color"] == "RED" and i["orders_30d"] == 0)

    data = [
        ["ЦЕНЫ — актуальные из Ozon API", "", "", "", "", "", "", "", "", ""],
        [f"всего SKU: {total}  |  🔴 RED: {red_count} (из них не продаются: {dead_red})  |  "
         f"убыточных на единицу: {loss_count}  |  обновлено {datetime.now().strftime('%H:%M')}",
         "", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", ""],
    ]'''

if old_sub in src:
    src = src.replace(old_sub, new_sub)
    print("[OK] подзаголовок обновлён")
else:
    print("[?] Не нашёл подзаголовок")

# Заголовки таблицы — добавляем Выручку и Заказы
old_hdr = '''    data.append(["Offer ID", "Название", "Себест", "Цена Ozon", "Min",
                 "Индекс", "Приб/ед", "Оценка"])

    for it in items:
        # Оценка
        if it["unit_profit"] < 0:
            verdict = "❌ Убыток"
        elif it["unit_margin"] < 0.05:
            verdict = "⚠ Тонко"
        elif it["unit_margin"] < 0.15:
            verdict = "✅ Норма"
        else:
            verdict = "🟢 Отлично"

        profit_str = f"{it['unit_profit']:+,.0f}" if it["unit_profit"] else "0"

        data.append([
            it["offer_id"],
            it["name"],
            f"{it['cost']:,.0f}",
            f"{it['price']:,.0f}",
            f"{it['min_price']:,.0f}" if it["min_price"] else "—",
            it["color"],
            profit_str,
            verdict,
        ])

    return data, items'''

new_hdr = '''    data.append(["Offer ID", "Название", "Себест", "Цена Ozon", "Min",
                 "Индекс", "Приб/ед", "Зак/30д", "Выручка/30д", "Оценка"])

    for it in items:
        # Умная оценка: маржа + продажи
        orders = it["orders_30d"]
        if it["unit_profit"] < 0:
            verdict = "❌ Убыток"
        elif orders == 0 and it["color"] == "RED":
            verdict = "🔴 Дорого + мёртвый"
        elif orders == 0 and it["unit_margin"] >= 0.15:
            verdict = "🤔 Дорого, не продаётся"
        elif orders == 0:
            verdict = "😴 Нет продаж"
        elif it["unit_margin"] < 0.05:
            verdict = "⚠ Тонко"
        elif it["unit_margin"] < 0.15:
            verdict = "✅ Норма"
        else:
            verdict = "🟢 Отлично"

        profit_str = f"{it['unit_profit']:+,.0f}" if it["unit_profit"] else "0"

        data.append([
            it["offer_id"],
            it["name"],
            f"{it['cost']:,.0f}",
            f"{it['price']:,.0f}",
            f"{it['min_price']:,.0f}" if it["min_price"] else "—",
            it["color"],
            profit_str,
            orders,
            f"{it['rev_30d']:,.0f}" if it["rev_30d"] else "—",
            verdict,
        ])

    return data, items'''

if old_hdr in src:
    src = src.replace(old_hdr, new_hdr)
    print("[OK] таблица: добавлены Зак/30д, Выручка/30д + умная оценка")
else:
    print("[?] Не нашёл таблицу")

# ============ 2. format_prices — обновляем ширины и форматирование ============
old_w = '''    # Ширины
    ops.append({"type": "width", "col": "A", "width": 130})
    ops.append({"type": "width", "col": "B", "width": 400})
    ops.append({"type": "width", "col": "C", "width": 90})
    ops.append({"type": "width", "col": "D", "width": 110})
    ops.append({"type": "width", "col": "E", "width": 90})
    ops.append({"type": "width", "col": "F", "width": 140})
    ops.append({"type": "width", "col": "G", "width": 90})
    ops.append({"type": "width", "col": "H", "width": 110})'''

new_w = '''    # Ширины
    ops.append({"type": "width", "col": "A", "width": 130})
    ops.append({"type": "width", "col": "B", "width": 380})
    ops.append({"type": "width", "col": "C", "width": 80})
    ops.append({"type": "width", "col": "D", "width": 100})
    ops.append({"type": "width", "col": "E", "width": 90})
    ops.append({"type": "width", "col": "F", "width": 130})
    ops.append({"type": "width", "col": "G", "width": 90})
    ops.append({"type": "width", "col": "H", "width": 80})
    ops.append({"type": "width", "col": "I", "width": 110})
    ops.append({"type": "width", "col": "J", "width": 150})'''

if old_w in src:
    src = src.replace(old_w, new_w)
    print("[OK] ширины обновлены (A-J)")

# Обновляем диапазоны в format_prices: H → J
src = src.replace('"range": "A1:H1"', '"range": "A1:J1"')
src = src.replace('"range": "A2:H2"', '"range": "A2:J2"')
src = src.replace('"range": "A4:H4"', '"range": "A4:J4"')
src = src.replace('"range": "A5:H5"', '"range": "A5:J5"')
src = src.replace('f"A{table_start}:H{table_start}"', 'f"A{table_start}:J{table_start}"')
src = src.replace('f"A{table_start}:H{last_row}"', 'f"A{table_start}:J{last_row}"')

# Заголовок unmerge/clear
src = src.replace('"range": "A1:Z500"', '"range": "A1:Z500"')  # уже так

# В loop данных — обновляем колонки H, I, J
old_data_fmt = '''        ops.append({"type": "format", "range": f"G{data_row}", "format": profit_fmt})
        # Оценка
        ops.append({"type": "format", "range": f"H{data_row}", "format": body_center})
        ops.append({"type": "row_height", "row": data_row, "height": 24})
        data_row += 1'''

new_data_fmt = '''        ops.append({"type": "format", "range": f"G{data_row}", "format": profit_fmt})
        # Зак/30д
        orders_val = it["orders_30d"]
        if orders_val == 0:
            order_fmt = CellFormat(textFormat=TextFormat(fontSize=10, italic=True, foregroundColor=MUTED_FG),
                                   horizontalAlignment='CENTER')
        else:
            order_fmt = body_center
        ops.append({"type": "format", "range": f"H{data_row}", "format": order_fmt})
        # Выручка/30д
        ops.append({"type": "format", "range": f"I{data_row}", "format": body_center})
        # Оценка
        ops.append({"type": "format", "range": f"J{data_row}", "format": body_center})
        ops.append({"type": "row_height", "row": data_row, "height": 24})
        data_row += 1'''

if old_data_fmt in src:
    src = src.replace(old_data_fmt, new_data_fmt)
    print("[OK] формат данных обновлён (H, I, J)")

# Примечания — сдвигаем на новые колонки
src = src.replace('"cell": "F5"', '"cell": "F5"')
src = src.replace('"cell": "G5"', '"cell": "G5"')
src = src.replace('"cell": "H5"', '"cell": "J5"')

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("\nГотово. Запускай: py sheets_sync.py")
