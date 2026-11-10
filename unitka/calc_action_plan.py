"""unitka/calc_action_plan.py — Умный план действий на основе rules.py."""
import gspread
from google.oauth2.service_account import Credentials
from datetime import date
from .db import connect
from . import config, rules

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
CRED = str(config.CREDENTIALS)
SHEET_ID = config.SHEET_ID
SHEET_TITLE = "План действий"


def collect_sku_data(cur):
    """Собирает паспорта всех активных SKU для проверки правилами."""
    # 1. Берем последние остатки
    cur.execute("SELECT MAX(date) FROM stock_daily")
    last_date = cur.fetchone()[0]
    if not last_date:
        return []

    cur.execute("""
        SELECT s.sku, s.fbo_present + s.fbs_present as stock, c.cost_price
        FROM stock_daily s
        LEFT JOIN (
            SELECT sku, cost_price FROM product_cost_history
            WHERE (sku, date_from) IN (SELECT sku, MAX(date_from) FROM product_cost_history GROUP BY sku)
        ) c ON s.sku = c.sku
        WHERE s.date = ? AND (s.fbo_present + s.fbs_present) > 0
    """, (last_date,))
    
    stocks = {str(r[0]): {"stock": r[1], "cost": r[2] or 0} for r in cur.fetchall()}

    # 2. Берем продажи за 30 дней для маржи и продаж за 14 дней
    cur.execute("""
        SELECT r.sku,
               SUM(r.sale_price + r.bonus + r.coinvestment) as revenue,
               SUM(r.quantity) as qty,
               SUM(CASE WHEN r.is_return = 0 THEN r.quantity * c.cost_price ELSE 0 END) as cogs
        FROM realization_daily r
        LEFT JOIN (
            SELECT sku, cost_price FROM product_cost_history
            WHERE (sku, date_from) IN (SELECT sku, MAX(date_from) FROM product_cost_history GROUP BY sku)
        ) c ON r.sku = c.sku
        WHERE r.date >= date('now', '-30 days')
        GROUP BY r.sku
    """)
    
    sales_30d = {}
    for r in cur.fetchall():
        sku = str(r[0])
        revenue = r[1] or 0
        qty = r[2] or 0
        cogs = r[3] or 0
        profit = revenue - cogs
        margin_pct = (profit / revenue * 100) if revenue > 0 else 0
        sales_30d[sku] = {
            "revenue_30d": revenue,
            "margin_pct": margin_pct,
            "sold_14d": int(qty / 2), # грубая оценка продаж за 14 дней
            "avg_price": (revenue / qty) if qty > 0 else 0
        }

    # 3. Собираем offer_id
    cur.execute("SELECT ozon_sku, offer_id FROM sku_map WHERE offer_id IS NOT NULL AND offer_id != ''")
    offers = {str(r[0]): r[1] for r in cur.fetchall()}

    # 4. Мин. цена (упрощенно: себестоимость * 1.5) - для точного расчета лучше использовать unit_core, но для теста сойдет
    # На самом деле в rules.py price_below_min будет срабатывать только если мы реально знаем цену. Возьмем среднюю цену продажи.

    all_skus = set(stocks.keys()) | set(sales_30d.keys())
    result = []

    for sku in all_skus:
        st = stocks.get(sku, {"stock": 0, "cost": 0})
        sale = sales_30d.get(sku, {"revenue_30d": 0, "margin_pct": 0, "sold_14d": 0, "avg_price": 0})
        
        # Простой расчет мин. цены (себестоимость + 15%)
        min_price = st["cost"] * 1.15 if st["cost"] else 0
        
        sku_data = {
            "sku": sku,
            "offer_id": offers.get(sku, ""),
            "stock": st["stock"],
            "cost": st["cost"],
            "price": sale["avg_price"], # Используем среднюю цену как текущую
            "min_price": min_price,
            "revenue_30d": sale["revenue_30d"],
            "margin_pct": sale["margin_pct"],
            "sold_14d": sale["sold_14d"],
            "avg_price": sale["avg_price"],
            "days_no_sales": 0 # Заглушка, для неликвида нужен сложный запрос
        }
        result.append(sku_data)
    return result


def main():
    conn = connect()
    cur = conn.cursor()
    
    print("Сбор данных по SKU...")
    skus = collect_sku_data(cur)
    conn.close()

    print(f"Проверка правил для {len(skus)} SKU...")
    all_tasks = []
    for sku_data in skus:
        tasks = rules.evaluate_sku(sku_data)
        all_tasks.extend(tasks)

    # Сортируем по деньгам (сначала самые дорогие потери)
    all_tasks.sort(key=lambda t: t.money_impact, reverse=True)

    # Выгружаем в Google Sheets
    creds = Credentials.from_service_account_file(CRED, scopes=SCOPES)
    client = gspread.authorize(creds)
    sh = client.open_by_key(SHEET_ID)
    
    try:
        ws = sh.worksheet(SHEET_TITLE)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=SHEET_TITLE, rows=200, cols=6)

    now_str = date.today().strftime("%Y-%m-%d")
    rows = [
        [f"УМНЫЙ ПЛАН ДЕЙСТВИЙ — {now_str}"],
        ["Срочность", "Артикул", "SKU", "Проблема", "Что делать", "Эффект, ₽"],
        []
    ]

    for t in all_tasks:
        sev = "🔴 КРИТИЧНО" if t.severity == 1 else ("🟡 ВАЖНО" if t.severity == 2 else "🟢 ИНФО")
        rows.append([
            sev, t.offer_id, t.sku, t.problem, t.action, round(t.money_impact, 2)
        ])

    ws.clear()
    ws.update(values=rows, range_name="A1", value_input_option="USER_ENTERED")

    # Форматирование
    reqs = [
        {"repeatCell": {"range": {"sheetId": ws.id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": 6},
         "cell": {"userEnteredFormat": {"backgroundColor": {"red": 0.18, "green": 0.33, "blue": 0.59}, "horizontalAlignment": "CENTER", "textFormat": {"bold": True, "fontSize": 14, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}}},
         "fields": "userEnteredFormat"}},
        {"repeatCell": {"range": {"sheetId": ws.id, "startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 0, "endColumnIndex": 6},
         "cell": {"userEnteredFormat": {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}}},
         "fields": "userEnteredFormat"}},
        {"updateDimensionProperties": {"range": {"sheetId": ws.id, "dimension": "COLUMNS", "startIndex": 3, "endIndex": 5}, "properties": {"pixelSize": 300}, "fields": "pixelSize"}}
    ]
    sh.batch_update({"requests": reqs})

    print(f"УСПЕХ! Найдено проблем: {len(all_tasks)}")
    print(f"Общий эффект: {sum(t.money_impact for t in all_tasks):,.0f} ₽")
    print("Лист 'План действий' обновлен.")

if __name__ == "__main__":
    main()