"""
patch_capital_pending.py — 2 правки листа КАПИТАЛ:
1. Убираем "В товаре в пути" из блока 1
2. Добавляем "В заказах к клиентам" в блок 3 (ПРОГНОЗ)
"""
src = open("sheets_sync.py", encoding="utf-8").read()

# === 1. В build_capital — убрать строку "В товаре в пути" ===
old1 = '''    data.append(["В товаре в пути", f"{in_transit:,.0f}", "0.0%",
                 "нет данных из API", ""])'''

new1 = ''  # убираем совсем

if old1 in src:
    src = src.replace(old1, new1)
    print("[OK] Строка 'В товаре в пути' удалена из блока 1")
else:
    print("[?] Не нашёл строку 'В товаре в пути'")

# === 2. В build_capital — получить сумму pending orders ===
old2 = '''    # === ПРОГНОЗ 14 ДНЕЙ ===
    today = datetime.now()'''

new2 = '''    # === ПРОГНОЗ 14 ДНЕЙ ===
    # Заказы в доставке
    pending = con.execute("""
        SELECT COUNT(*), SUM(total_price) FROM pending_orders
        WHERE status IN ('delivering', 'sent_by_seller')
    """).fetchone()
    pending_count = pending[0] or 0
    pending_amount = pending[1] or 0

    today = datetime.now()'''

if old2 in src:
    src = src.replace(old2, new2)
    print("[OK] pending_orders подключён")

# === 3. В блок 3 — добавить строку после приходов от Ozon ===
old3 = '''    # План закупок
    if payments:
        for p in payments:
            data.append(["Платёж: " + (p[1] or "?"), p[0], f"-{p[2]:,.0f}", "", ""])'''

new3 = '''    # Заказы к клиентам
    if pending_amount > 0:
        data.append([f"В заказах к клиентам ({pending_count} шт)",
                     "в доставке",
                     f"{pending_amount:,.0f}",
                     "уже продано, деньги после получения", ""])

    # План закупок
    if payments:
        for p in payments:
            data.append(["Платёж: " + (p[1] or "?"), p[0], f"-{p[2]:,.0f}", "", ""])'''

if old3 in src:
    src = src.replace(old3, new3)
    print("[OK] Строка о pending orders добавлена в блок 3")

# === 4. Обновить format_capital: было 10 строк в блоке 1, стало 9 ===
# Строки 6-12: было 7 позиций (На счету, У Ozon, В товаре, В пути, ИТОГО, Резерв, ЧИСТЫЕ)
# Стало 6 позиций (На счету, У Ozon, В товаре, ИТОГО, Резерв, ЧИСТЫЕ)

# Обновляем merge и формат
old_fmt = '''    # Строки 6-9 — активы (на счету, у Ozon, в товаре, в пути)
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
    ops.append({"type": "row_height", "row": 12, "height": 30})'''

new_fmt = '''    # Строки 6-8 — активы (на счету, у Ozon, в товаре)
    for r in range(6, 9):
        ops.append({"type": "format", "range": f"A{r}", "format": label_fmt})
        ops.append({"type": "format", "range": f"B{r}:C{r}", "format": value_fmt})
        ops.append({"type": "row_height", "row": r, "height": 30})

    # Строка 9 — ИТОГО АКТИВОВ (синяя)
    ops.append({"type": "format", "range": "A9", "format": total_fmt})
    ops.append({"type": "format", "range": "B9:C9", "format": total_val_fmt})
    ops.append({"type": "row_height", "row": 9, "height": 30})

    # Строка 10 — Резерв налога
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
    ops.append({"type": "format", "range": "A10", "format": minus_fmt})
    ops.append({"type": "format", "range": "B10:C10", "format": minus_val_fmt})
    ops.append({"type": "row_height", "row": 10, "height": 30})

    # Строка 11 — ЧИСТЫЕ АКТИВЫ
    ops.append({"type": "format", "range": "A11", "format": net_fmt})
    ops.append({"type": "format", "range": "B11:C11", "format": net_val_fmt})
    ops.append({"type": "row_height", "row": 11, "height": 30})'''

if old_fmt in src:
    src = src.replace(old_fmt, new_fmt)
    print("[OK] format_capital: блок 1 — 6 строк вместо 7")

# === 5. Сдвигаем блоки 2, 3, 4, 5 на -1 строку ===
# Блок 2: было 14 (заголовок), 15 (шапка), 16-20 (5 строк), 21 (МОЖНО ЗАБРАТЬ)
# Стало: 13, 14, 15-19, 20
src = src.replace('"range": "A14:E14"', '"range": "A13:E13"')
src = src.replace('"range": "A15:E15", "format": tbl_hdr', '"range": "A14:E14", "format": tbl_hdr')
src = src.replace('for r in range(16, 21):', 'for r in range(15, 20):')
src = src.replace('"range": "A21", "format": free_fmt', '"range": "A20", "format": free_fmt')
src = src.replace('"range": "B21:C21", "format": free_val_fmt', '"range": "B20:C20", "format": free_val_fmt')
src = src.replace('"row": 21, "height": 34', '"row": 20, "height": 34')

# Блок 3: было 23 (заголовок), 24 (шапка), 25-29 (данные) 
# Стало: 22, 23, 24-29
src = src.replace('"range": "A23:E23"', '"range": "A22:E22"')
src = src.replace('"range": "A24:E24", "format": tbl_hdr', '"range": "A23:E23", "format": tbl_hdr')
src = src.replace('for r in range(25, 30):', 'for r in range(24, 30):')  # 6 строк на прогноз

# Блок 4: было 31, 32, 33-37
src = src.replace('"range": "A31:E31"', '"range": "A31:E31"')  # оставляем (был сдвиг)
src = src.replace('"range": "A32:E32", "format": tbl_hdr', '"range": "A32:E32", "format": tbl_hdr')
# Не трогаем пока

print("[OK] format_capital: блоки сдвинуты")

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print()
print("Готово. Запускай: py sheets_sync.py")
