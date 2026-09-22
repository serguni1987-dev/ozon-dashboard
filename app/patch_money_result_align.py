"""
patch_money_result_align.py — выравнивает структуру строк в ДЕНЬГИ и РЕЗУЛЬТАТ.
Структура:
  1: заголовок (синий)
  2: подзаголовок (серый)
  3: пусто
  4: заголовки таблицы (синие)
  5+: данные
"""
import re

src = open("sheets_sync.py", encoding="utf-8").read()

# ============ НОВЫЙ build_money ============
new_build_money = '''def build_money(con):
    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    periods = [
        ("7 дней", (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d"), max_date),
        ("30 дней", (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d"), max_date),
        ("весь период", con.execute("SELECT MIN(date) FROM sales_daily").fetchone()[0], max_date),
    ]

    data = [
        ["ДЕНЬГИ", "", "", "", "", "", "", "", ""],
        [f"ставки: комиссия {COMMISSION_PCT*100:.2f}%, услуги {SERVICES_PCT*100:.1f}%",
         "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", ""],
        ["Период", "Выручка", "Себестоимость", "Комиссия", "Услуги Ozon",
         "Прибыль", "Маржа", "Заказов", "Ср. чек"],
    ]

    for label, d1, d2 in periods:
        rows = con.execute("""
            SELECT p.sku, p.cost_price,
                   SUM(sd.revenue) AS revenue,
                   SUM(sd.orders_units) AS orders
            FROM sales_daily sd
            JOIN products p ON p.sku = sd.sku
            WHERE sd.date BETWEEN ? AND ?
              AND p.is_own = 1 AND p.is_archived = 0
            GROUP BY p.sku
        """, (d1, d2)).fetchall()

        rev = cost = comm = serv = profit = 0.0
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
            comm += cm
            serv += sv
            profit += pb - tx
            orders += o
        margin = profit / rev if rev else 0
        avg = rev / orders if orders else 0

        data.append([
            label,
            f"{rev:,.0f}", f"{cost:,.0f}", f"{comm:,.0f}", f"{serv:,.0f}",
            f"{profit:,.0f}", f"{margin:.3f}", orders, f"{avg:,.0f}",
        ])

    data.append(["", "", "", "", "", "", "", "", ""])
    data.append([f"PremiumSubscription {PREMIUM_FIXED:,.0f} ₽/мес — постоянный расход, не в марже",
                 "", "", "", "", "", "", "", ""])
    return data
'''

# Заменяем build_money
pattern = re.compile(r"def build_money\(con\):.*?(?=\ndef build_result)", re.DOTALL)
src, n = pattern.subn(new_build_money + "\n\n", src)
print(f"[{'OK' if n else 'FAIL'}] build_money переписан")

# ============ НОВЫЙ build_result ============
new_build_result = '''def build_result(con):
    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    min_date = con.execute("SELECT MIN(date) FROM sales_daily").fetchone()[0]

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

    data = [
        ["РЕЗУЛЬТАТ", "", "", ""],
        [f"период {min_date} — {max_date}", "", "", ""],
        ["", "", "", ""],
        ["Показатель", "Сейчас", "Прошлый запуск", "Δ"],
    ]

    def delta(c, o):
        if not o:
            return "—"
        return f"{(c - o) / abs(o) * 100:+.1f}%"

    if prev:
        p_run, p_rev, p_profit, p_margin, p_orders, p_avg = prev
        data.append(["Выручка", f"{rev:,.0f}", f"{p_rev:,.0f}", delta(rev, p_rev)])
        data.append(["Прибыль", f"{profit:,.0f}", f"{p_profit:,.0f}", delta(profit, p_profit)])
        data.append(["Маржа", f"{margin*100:.1f}%", f"{p_margin*100:.1f}%", ""])
        data.append(["Заказы", orders, p_orders, delta(orders, p_orders)])
        data.append(["Ср. чек", f"{avg:,.0f}", f"{p_avg:,.0f}", delta(avg, p_avg)])
        data.append(["", "", "", ""])
        data.append([f"Предыдущий запуск: {p_run}", "", "", ""])
    else:
        data.append(["Выручка", f"{rev:,.0f}", "—", "первый запуск"])
        data.append(["Прибыль", f"{profit:,.0f}", "—", ""])
        data.append(["Маржа", f"{margin*100:.1f}%", "—", ""])
        data.append(["Заказов", orders, "—", ""])
        data.append(["Ср. чек", f"{avg:,.0f}", "—", ""])

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    con.execute("""
        INSERT OR REPLACE INTO dashboard_snapshots
        (run_at, period_from, period_to, revenue, profit, margin, orders, avg_check)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (now, min_date, max_date, rev, profit, margin, orders, avg))
    con.commit()

    return data
'''

pattern = re.compile(r"def build_result\(con\):.*?(?=\n\ndef main)", re.DOTALL)
src, n = pattern.subn(new_build_result + "\n\n", src)
print(f"[{'OK' if n else 'FAIL'}] build_result переписан")

# ============ ИСПРАВЛЯЕМ format_money ============
# Убираем лишний merge и сдвигаем tbl_hdr на строку 4 (уже так), но данные 5-7
# Premium в строке 9 (уже так)

# Заголовок A1:I1, подзаголовок A2:I2 — уже так
# Всё ок

# ============ ИСПРАВЛЯЕМ format_result ============
# Заголовок A1:D1, подзаголовок A2:D2, tbl_hdr на A4:D4, данные 5-9, last_run 11 — всё так

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("\nГотово. Запускай: py sheets_sync.py")
