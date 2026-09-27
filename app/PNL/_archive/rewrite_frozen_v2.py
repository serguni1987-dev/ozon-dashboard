import re
src = open("sheets_sync.py", encoding="utf-8").read()

# Удаляем build_frozen
pattern = re.compile(r"def build_frozen\(con\):.*?(?=\ndef format_frozen)", re.DOTALL)
src, n = pattern.subn("", src)
print(f"[OK] Старый build_frozen удалён: {n}")

new_build = '''def build_frozen(con):
    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    date_from = (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")

    rows = con.execute("""
        SELECT cs.offer_id, cs.total_present AS stock,
               p.name, p.cost_price,
               COALESCE(sd.orders, 0) AS orders_30d,
               cp.price_index_color AS color
        FROM current_stocks cs
        JOIN products p ON p.offer_id = cs.offer_id
        LEFT JOIN current_prices cp ON cp.offer_id = cs.offer_id
        LEFT JOIN (
            SELECT sku, SUM(orders_units) AS orders
            FROM sales_daily WHERE date >= ? GROUP BY sku
        ) sd ON sd.sku = p.sku
        WHERE cs.total_present > 0
          AND p.is_own = 1 AND p.is_archived = 0
          AND p.cost_price > 0
    """, (date_from,)).fetchall()

    items = []
    for r in rows:
        stock = r["stock"] or 0
        cost = r["cost_price"] or 0
        frozen = stock * cost
        orders = r["orders_30d"] or 0
        days = stock / (orders / 30) if orders > 0 else 999
        items.append({
            "offer_id": r["offer_id"],
            "name": (r["name"] or "")[:55],
            "stock": int(stock),
            "cost": cost,
            "frozen": frozen,
            "orders_30d": orders,
            "days_to_sell": days,
            "color": r["color"] or "",
        })
    items.sort(key=lambda x: -x["frozen"])

    total_frozen = sum(i["frozen"] for i in items)
    dead = [i for i in items if i["orders_30d"] == 0]
    dead_money = sum(i["frozen"] for i in dead)
    dead_pct = (dead_money / total_frozen * 100) if total_frozen else 0
    infinite = [i for i in items if i["days_to_sell"] == 999]
    slow = [i for i in items if 30 < i["days_to_sell"] < 999]
    slow_money = sum(i["frozen"] for i in slow)
    fast = [i for i in items if i["days_to_sell"] <= 30]
    fast_money = sum(i["frozen"] for i in fast)
    big_frozen = [i for i in items if i["frozen"] >= 5000]

    # === Тезисы выводов ===
    if dead_pct > 50:
        v1 = f"❌ {len(dead)} SKU мёртвых = {dead_money:,.0f} ₽ ({dead_pct:.0f}%) — деньги стоят без дела"
    elif dead_pct > 25:
        v1 = f"⚠ {len(dead)} SKU мёртвых = {dead_money:,.0f} ₽ ({dead_pct:.0f}%) — половина склада не двигается"
    elif dead_money > 0:
        v1 = f"✅ Мёртвых мало: {len(dead)} SKU = {dead_money:,.0f} ₽ ({dead_pct:.0f}%)"
    else:
        v1 = "✅ Все SKU с остатком продаются"

    if infinite:
        v2 = f"🔴 {len(infinite)} SKU вообще не продавались — разобраться в первую очередь"
    elif slow:
        v2 = f"⏳ {len(slow)} SKU продаются медленно (>30 дней) = {slow_money:,.0f} ₽"
    else:
        v2 = "✅ Оборачиваемость в норме"

    if big_frozen:
        top3 = ", ".join(i["offer_id"] for i in big_frozen[:3])
        v3 = f"→ Крупные заморозки (≥5000 ₽): {len(big_frozen)} SKU ({top3}...) — начинать с них"
    else:
        v3 = "→ Крупных заморозок нет — работать по мелочи"

    if fast_money > 0:
        v4 = f"💰 {len(fast)} SKU продаются быстро (≤30 дней) = {fast_money:,.0f} ₽ — не трогать"
    else:
        v4 = ""

    if dead_money > 50000:
        v5 = f"→ ИТОГ: освободить {dead_money:,.0f} ₽ из мёртвых SKU — главная цель"
    elif dead_money > 0:
        v5 = f"→ ИТОГ: {dead_money:,.0f} ₽ можно освободить"
    else:
        v5 = "→ ИТОГ: склад работает нормально"

    # === Сборка data — все заголовки и выводы в колонке A ===
    data = []
    # 1: заголовок
    data.append(["ЗАМОРОЗКА В СКЛАДЕ", "", "", "", "", "", "", ""])
    # 2: подзаголовок
    data.append([f"актуально из Ozon API на {datetime.now().strftime('%d.%m %H:%M')}", "", "", "", "", "", "", ""])
    # 3: пусто
    data.append(["", "", "", "", "", "", "", ""])
    # 4: ИТОГИ
    data.append(["ИТОГИ", "", "", "", "", "", "", ""])
    # 5-7: итоги (значение в колонке A, чтобы merge A:B не съел)
    data.append([f"SKU с остатком", len(items), "", "", "", "", "", ""])
    data.append([f"Всего заморожено", f"{total_frozen:,.0f} ₽", "", "", "", "", "", ""])
    data.append([f"Мёртвые (0 продаж 30д)", f"{len(dead)} SKU = {dead_money:,.0f} ₽",
                 f"({dead_pct:.0f}%)", "", "", "", "", ""])
    # 8: пусто
    data.append(["", "", "", "", "", "", "", ""])
    # 9: ВЫВОДЫ
    data.append(["ВЫВОДЫ", "", "", "", "", "", "", ""])
    # 10-14: 5 тезисов — все в колонке A
    data.append([v1, "", "", "", "", "", "", ""])
    data.append([v2, "", "", "", "", "", "", ""])
    data.append([v3, "", "", "", "", "", "", ""])
    data.append([v4, "", "", "", "", "", "", ""])
    data.append([v5, "", "", "", "", "", "", ""])
    # 15: пусто
    data.append(["", "", "", "", "", "", "", ""])
    # 16: ТОП-30
    data.append(["ТОП-30 ПО ЗАМОРОЗКЕ", "", "", "", "", "", "", ""])
    # 17: заголовки
    data.append(["#", "Offer ID", "Название", "Ост", "Себест", "Замор", "Дней", "Индекс"])
    # 18+: данные
    for i, it in enumerate(items[:30], 1):
        days_str = f"{it['days_to_sell']:.0f}" if it['days_to_sell'] < 999 else "∞"
        data.append([i, it["offer_id"], it["name"], it["stock"],
                     f"{it['cost']:,.0f}", f"{it['frozen']:,.0f}",
                     days_str, it["color"]])

    return data, items


'''

# Вставляем новый build_frozen перед format_frozen
anchor = "def format_frozen(ws, items):"
if anchor in src:
    src = src.replace(anchor, new_build + anchor, 1)
    print("[OK] Новый build_frozen вставлен")

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("\\nГотово. Запускай: py sheets_sync.py")
