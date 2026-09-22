"""
patch_result_verdicts.py — колонка E «Оценка» + блок ВЫВОДЫ.
"""
import re

src = open("sheets_sync.py", encoding="utf-8").read()

# ============ НОВЫЙ build_result ============
new_build_result = '''def build_result(con):
    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    min_date = "2026-08-01"

    rows = con.execute("""
        SELECT p.sku, p.cost_price,
               SUM(sd.revenue) AS revenue,
               SUM(sd.orders_units) AS orders
        FROM sales_daily sd
        JOIN products p ON p.sku = sd.sku
        WHERE sd.date BETWEEN ? AND ?
          AND p.is_own = 1 AND p.is_archived = 0
        GROUP BY p.sku
    """, (min_date, max_date)).fetchall()

    rev = cost = profit = 0.0
    orders = 0
    for sku, cost_price, r, o in rows:
        r = r or 0
        o = o or 0
        cost_price = cost_price or 0
        c = cost_price * o
        cm = r * COMMISSION_PCT
        sv = r * SERVICES_PCT
        pb = r - c - cm - sv
        tx = pb * TAX_PCT if pb > 0 else 0
        rev += r
        cost += c
        profit += pb - tx
        orders += o
    margin = profit / rev if rev else 0
    avg = rev / orders if orders else 0

    con.execute("""
        CREATE TABLE IF NOT EXISTS dashboard_snapshots (
            run_at TEXT PRIMARY KEY,
            period_from TEXT, period_to TEXT,
            revenue REAL, profit REAL, margin REAL,
            orders INTEGER, avg_check REAL
        )
    """)
    con.commit()
    prev = con.execute("""
        SELECT run_at, revenue, profit, margin, orders, avg_check
        FROM dashboard_snapshots ORDER BY run_at DESC LIMIT 1
    """).fetchone()

    def delta(c, o):
        if not o:
            return "—"
        return f"{(c - o) / abs(o) * 100:+.1f}%"

    def verdict_delta(d_str):
        """Оценка по Δ-строке."""
        if d_str == "—" or d_str == "первый запуск":
            return "первый запуск"
        try:
            v = float(d_str.rstrip("%"))
        except ValueError:
            return "—"
        if v > 5:
            return "🟢 Существенный рост"
        if v > 1:
            return "✅ Рост"
        if v > -1:
            return "➖ Без изменений"
        if v > -5:
            return "⚠ Снижение"
        return "❌ Падение"

    data = [
        ["РЕЗУЛЬТАТ", "", "", "", ""],
        [f"период с 1 августа по {max_date}  (реальный старт бизнеса)", "", "", "", ""],
        ["", "", "", "", ""],
        ["Показатель", "Сейчас", "Прошлый запуск", "Δ", "Оценка"],
    ]

    if prev:
        p_run, p_rev, p_profit, p_margin, p_orders, p_avg = prev
        d_rev = delta(rev, p_rev)
        d_profit = delta(profit, p_profit)
        d_orders = delta(orders, p_orders)
        d_avg = delta(avg, p_avg)

        data.append(["Выручка", f"{rev:,.0f}", f"{p_rev:,.0f}", d_rev, verdict_delta(d_rev)])
        data.append(["Прибыль", f"{profit:,.0f}", f"{p_profit:,.0f}", d_profit, verdict_delta(d_profit)])
        data.append(["Маржа", f"{margin*100:.1f}%", f"{p_margin*100:.1f}%", "", ""])
        data.append(["Заказы", orders, p_orders, d_orders, verdict_delta(d_orders)])
        data.append(["Ср. чек", f"{avg:,.0f}", f"{p_avg:,.0f}", d_avg, verdict_delta(d_avg)])
    else:
        data.append(["Выручка", f"{rev:,.0f}", "—", "первый запуск", "—"])
        data.append(["Прибыль", f"{profit:,.0f}", "—", "первый запуск", "—"])
        data.append(["Маржа", f"{margin*100:.1f}%", "—", "—", "—"])
        data.append(["Заказов", orders, "—", "первый запуск", "—"])
        data.append(["Ср. чек", f"{avg:,.0f}", "—", "первый запуск", "—"])

    # === ВЫВОДЫ ===
    data.append(["", "", "", "", ""])
    data.append(["ВЫВОДЫ", "", "", "", ""])

    # Если есть предыдущий запуск — считаем тезисы
    if prev:
        p_run, p_rev, p_profit, p_margin, p_orders, p_avg = prev

        # 1. Общая динамика по выручке
        if p_rev:
            rev_chg = (rev - p_rev) / abs(p_rev) * 100
            if rev_chg > 5:
                v1 = f"🟢 Выручка выросла на {rev_chg:+.1f}% — рост оборотов"
            elif rev_chg > 1:
                v1 = f"✅ Выручка выросла на {rev_chg:+.1f}% — небольшой рост"
            elif rev_chg > -1:
                v1 = f"➖ Выручка без изменений ({rev_chg:+.1f}%)"
            elif rev_chg > -5:
                v1 = f"⚠ Выручка снизилась на {rev_chg:+.1f}% — обратить внимание"
            else:
                v1 = f"❌ Выручка упала на {rev_chg:+.1f}% — разобраться с причинами"
        else:
            v1 = "Нет данных для сравнения выручки"

        # 2. Прибыль vs выручка — что растёт быстрее
        if p_profit and p_rev:
            profit_chg = (profit - p_profit) / abs(p_profit) * 100
            if profit_chg > rev_chg + 2:
                v2 = f"✅ Прибыль растёт быстрее выручки ({profit_chg:+.1f}% vs {rev_chg:+.1f}%) — маржа улучшается"
            elif profit_chg < rev_chg - 2:
                v2 = f"⚠ Прибыль падает быстрее выручки ({profit_chg:+.1f}% vs {rev_chg:+.1f}%) — маржа ухудшается"
            else:
                v2 = f"➖ Прибыль и выручка меняются одинаково ({profit_chg:+.1f}% vs {rev_chg:+.1f}%)"
        else:
            v2 = "Прибыль: нет данных для сравнения"

        # 3. Маржа
        m_prev_pct = p_margin * 100 if p_margin else 0
        m_curr_pct = margin * 100
        d_m = m_curr_pct - m_prev_pct
        if d_m > 1:
            v3 = f"✅ Маржа выросла: {m_prev_pct:.1f}% → {m_curr_pct:.1f}% ({d_m:+.1f} п.п.)"
        elif d_m < -1:
            v3 = f"⚠ Маржа упала: {m_prev_pct:.1f}% → {m_curr_pct:.1f}% ({d_m:+.1f} п.п.)"
        else:
            v3 = f"➖ Маржа стабильна: {m_curr_pct:.1f}%"

        # 4. Средний чек
        if p_avg:
            avg_chg = (avg - p_avg) / abs(p_avg) * 100
            if avg_chg > 3:
                v4 = f"🟢 Средний чек вырос на {avg_chg:+.1f}% — клиенты берут дороже"
            elif avg_chg < -3:
                v4 = f"⚠ Средний чек упал на {avg_chg:+.1f}% — клиенты берут дешевле"
            else:
                v4 = f"➖ Средний чек стабилен: {avg:,.0f} ₽"
        else:
            v4 = f"Средний чек: {avg:,.0f} ₽"

        # 5. Общий вердикт
        if rev_chg > 1 and profit_chg > 1:
            v5 = "→ ИТОГ: бизнес растёт — продолжать в том же направлении"
        elif rev_chg < -1 and profit_chg < -1:
            v5 = "→ ИТОГ: бизнес сжимается — проверить убыточные SKU и цены"
        elif rev_chg > 0 and profit_chg < 0:
            v5 = "→ ИТОГ: обороты растут, но прибыль падает — растёт доля низкомаржинальных SKU"
        else:
            v5 = "→ ИТОГ: стабильность — использовать время для оптимизации"
    else:
        v1 = f"Первый запуск: выручка {rev:,.0f} ₽, прибыль {profit:,.0f} ₽"
        v2 = f"Маржа {margin*100:.1f}% — сравнение появится со следующего запуска"
        v3 = "→ Запусти py sheets_sync.py повторно, чтобы увидеть динамику"
        v4 = ""
        v5 = ""

    data.append([v1, "", "", "", ""])
    data.append([v2, "", "", "", ""])
    data.append([v3, "", "", "", ""])
    if v4:
        data.append([v4, "", "", "", ""])
    if v5:
        data.append([v5, "", "", "", ""])

    data.append(["", "", "", "", ""])
    data.append([f"Предыдущий запуск: {prev[0] if prev else 'нет'}", "", "", "", ""])

    # Запись снапшота
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    con.execute("""
        INSERT OR REPLACE INTO dashboard_snapshots
        (run_at, period_from, period_to, revenue, profit, margin, orders, avg_check)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (now, min_date, max_date, rev, profit, margin, orders, avg))
    con.commit()

    return data
'''

pattern = re.compile(r"def build_result\(con\):.*?(?=\n\ndef |\Z)", re.DOTALL)
src, n = pattern.subn(new_build_result + "\n\n", src)
print(f"[{'OK' if n else 'FAIL'}] build_result переписан")

# ============ НОВЫЙ format_result ============
new_format_result = '''def format_result(ws):
    sid = ws.id
    ops = []

    ops.append({"type": "unmerge", "range": "A1:Z50"})
    ops.append({"type": "clear_notes", "range": "A1:Z50"})

    # Заголовок A1:E1
    ops.append({"type": "merge", "range": "A1:E1"})
    ops.append({"type": "format", "range": "A1:E1", "format": FMT_TITLE})
    ops.append({"type": "row_height", "row": 1, "height": 40})

    # Подзаголовок A2:E2
    sub_fmt = CellFormat(
        textFormat=TextFormat(fontSize=11, italic=True, foregroundColor=Color(0.35, 0.35, 0.35)),
        backgroundColor=SUBHEADER_BG,
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "merge", "range": "A2:E2"})
    ops.append({"type": "format", "range": "A2:E2", "format": sub_fmt})
    ops.append({"type": "row_height", "row": 2, "height": 26})

    # Заголовки A4:E4
    tbl_hdr = CellFormat(
        backgroundColor=HEADER_BG,
        textFormat=TextFormat(bold=True, fontSize=11, foregroundColor=HEADER_FG),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "format", "range": "A4:E4", "format": tbl_hdr})
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
    body_verdict = CellFormat(
        textFormat=TextFormat(fontSize=11),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )

    for r in range(5, 10):
        ops.append({"type": "format", "range": f"A{r}", "format": body_label})
        ops.append({"type": "format", "range": f"B{r}:C{r}", "format": body_val})
        ops.append({"type": "format", "range": f"D{r}", "format": body_delta})
        ops.append({"type": "format", "range": f"E{r}", "format": body_verdict})
        ops.append({"type": "row_height", "row": r, "height": 32})

    # ВЫВОДЫ — строка 11
    ops.append({"type": "merge", "range": "A11:E11"})
    ops.append({"type": "format", "range": "A11:E11", "format": FMT_SUBHEADER})
    ops.append({"type": "row_height", "row": 11, "height": 28})

    # Строки выводов 12-16 (5 максимум)
    for r in range(12, 17):
        ops.append({"type": "merge", "range": f"A{r}:E{r}"})
        ops.append({"type": "row_height", "row": r, "height": 30})

    # Строка "Предыдущий запуск" — 18
    last_run = CellFormat(
        textFormat=TextFormat(fontSize=10, italic=True, foregroundColor=MUTED_FG),
        horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
    )
    ops.append({"type": "merge", "range": "A18:E18"})
    ops.append({"type": "format", "range": "A18:E18", "format": last_run})
    ops.append({"type": "row_height", "row": 18, "height": 24})

    # Ширины
    ops.append({"type": "width", "col": "A", "width": 160})
    ops.append({"type": "width", "col": "B", "width": 150})
    ops.append({"type": "width", "col": "C", "width": 150})
    ops.append({"type": "width", "col": "D", "width": 100})
    ops.append({"type": "width", "col": "E", "width": 240})

    ops.append({"type": "frozen", "rows": 4})

    ops.append({"type": "note", "cell": "D4",
                "note": "Δ = изменение vs прошлый запуск. Зелёный: рост, красный: падение."})
    ops.append({"type": "note", "cell": "E4",
                "note": "Оценка автоматическая: 🟢 рост >5%, ✅ 1-5%, ➖ ±1%, ⚠ -1..-5%, ❌ <-5%."})
    ops.append({"type": "note", "cell": "A11",
                "note": "Автоматические выводы. Обновляются при каждом запуске."})

    n = batch_apply(ws, sid, ops)
    print(f"  Основное форматирование: {n}")

    # Δ-цвета
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
            print(f"  Δ-цвета: {n2}")
    except Exception as e:
        print(f"  [WARN] Δ-цвета: {e}")

    # Цвет выводов 12-16
    try:
        vals = ws.get("A12:A16")
        ops3 = []
        for i, row in enumerate(vals):
            if not row:
                continue
            v = row[0]
            r = 12 + i
            if v.startswith("❌") or v.startswith("⚠"):
                bg, fg = BAD_BG, BAD_FG
            elif v.startswith("✅") or v.startswith("🟢"):
                bg, fg = GOOD_BG, GOOD_FG
            elif v.startswith("→"):
                bg, fg = Color(0.90, 0.94, 1.0), Color(0.10, 0.20, 0.50)
            else:
                bg, fg = SUBHEADER_BG, Color(0.2, 0.2, 0.2)
            ops3.append({"type": "format", "range": f"A{r}:E{r}", "format": CellFormat(
                backgroundColor=bg,
                textFormat=TextFormat(fontSize=11, foregroundColor=fg),
                horizontalAlignment='LEFT', verticalAlignment='MIDDLE', wrapStrategy='WRAP',
            )})
        if ops3:
            n3 = batch_apply(ws, sid, ops3)
            print(f"  Цвет выводов: {n3}")
    except Exception as e:
        print(f"  [WARN] Цвет выводов: {e}")


def sync_result(sh, con):
    print("\\n[Лист РЕЗУЛЬТАТ]")
    ws = get_or_create_sheet(sh, "РЕЗУЛЬТАТ")
    data = build_result(con)
    clear_and_write(ws, data)
    print(f"  Записано строк: {len(data)}")
    format_result(ws)


'''

pattern = re.compile(r"def format_result\(ws\):.*?(?=\n\ndef main)", re.DOTALL)
src, n = pattern.subn(new_format_result + "\n\n", src)
print(f"[{'OK' if n else 'FAIL'}] format_result переписан")

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("\nГотово. Запускай: py sheets_sync.py")
