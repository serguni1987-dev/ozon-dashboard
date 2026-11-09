import os
import json
import gspread
from google.oauth2.service_account import Credentials
from .db import connect

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRED = os.path.join(APP_DIR, "app", "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SHEET_ID = "1Or2Gak6ihm00rM7ZNF4YvGcEPi6ULLadKIgBjnQZ6q0"

def build():
    conn = connect()
    cur = conn.cursor()

    # 1. Загружаем offer_id из sku_map
    offer_map = {}
    try:
        cur.execute("SELECT ozon_sku, offer_id FROM sku_map WHERE offer_id IS NOT NULL AND offer_id != ''")
        for r in cur.fetchall():
            offer_map[str(r[0])] = r[1]
    except Exception as e:
        print(f"Ошибка чтения sku_map: {e}")

    # 2. Получаем список АКТИВНЫХ SKU: есть на остатках или продавались за последние 30 дней
    active_skus = set()
    
    # 2.1 SKU с остатками > 0 на последнюю дату
    cur.execute("SELECT MAX(date) FROM stock_daily")
    last_date = cur.fetchone()[0]
    if last_date:
        cur.execute("SELECT sku FROM stock_daily WHERE date = ? AND (fbo_present + fbs_present) > 0", (last_date,))
        for r in cur.fetchall():
            active_skus.add(str(r[0]))
    
    # 2.2 SKU, которые продавались за последние 30 дней
    cur.execute("SELECT DISTINCT sku FROM realization_daily WHERE date >= date('now', '-30 days') AND is_return = 0")
    for r in cur.fetchall():
        active_skus.add(str(r[0]))
    
    print(f"Активных SKU (есть на остатках или продавались за 30 дней): {len(active_skus)}")

    # 3. Основной запрос по всем SKU (для общей прибыли)
    cur.execute("""
        SELECT 
            r.sku,
            COALESCE(SUM(r.sale_price + r.bonus + r.coinvestment), 0) AS revenue,
            COALESCE(SUM(CASE WHEN r.is_return = 0 THEN r.quantity * c.cost_price ELSE 0 END), 0) AS cogs,
            COALESCE(SUM(s.total_exp), 0) AS ozon_exp
        FROM realization_daily r
        LEFT JOIN (
            SELECT sku, cost_price FROM product_cost_history 
            WHERE (sku, date_from) IN (SELECT sku, MAX(date_from) FROM product_cost_history GROUP BY sku)
        ) c ON r.sku = c.sku
        LEFT JOIN (SELECT sku, date, SUM(ABS(amount)) as total_exp FROM accrual_sku_daily GROUP BY sku, date) s ON r.sku = s.sku AND r.date = s.date
        WHERE r.date LIKE '2026-%'
        GROUP BY r.sku
    """)
    rows = cur.fetchall()
    conn.close()

    items = []
    total_revenue = 0
    total_cogs = 0
    total_exp = 0
    total_profit = 0

    for sku, revenue, cogs, exp in rows:
        # Пропускаем SKU, которых нет на остатках и не было продаж за 30 дней
        if str(sku) not in active_skus:
            # Но учитываем в общей прибыли (total_profit)
            total_revenue += revenue
            total_cogs += cogs
            total_exp += exp
            total_profit += (revenue - cogs - exp)
            continue
        
        profit = revenue - cogs - exp
        min_price = (cogs + exp) * 1.15 if (cogs + exp) > 0 else 0
        offer_id = offer_map.get(str(sku), '')
        status = "Убыточный" if profit < 0 else "Прибыльный"
        margin = (profit / revenue * 100) if revenue != 0 else 0
        items.append({
            'offer_id': offer_id,
            'sku': sku,
            'revenue': revenue,
            'cogs': cogs,
            'exp': exp,
            'profit': profit,
            'min_price': min_price,
            'status': status,
            'margin': margin
        })
        total_revenue += revenue
        total_cogs += cogs
        total_exp += exp
        total_profit += profit

    # Сортируем по прибыли (возрастание, чтобы убыточные сверху)
    items.sort(key=lambda x: x['profit'])

    return {
        'total_revenue': total_revenue,
        'total_cogs': total_cogs,
        'total_exp': total_exp,
        'total_profit': total_profit,
        'items': items
    }

def main():
    data = build()
    creds = Credentials.from_service_account_file(CRED, scopes=SCOPES)
    client = gspread.authorize(creds)
    sh = client.open_by_key(SHEET_ID)

    try:
        ws = sh.worksheet("Юнит-сводка")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title="Юнит-сводка", rows=200, cols=12)
    ws.clear()

    # Заголовок
    ws.update(values=[["ЮНИТ-СВОДКА: ДЕТАЛИЗАЦИЯ ПО SKU"]], range_name="A1")
    try: ws.merge_cells("A1:I1")
    except: pass
    ws.format("A1", {"backgroundColor": {"red": 0.18, "green": 0.33, "blue": 0.59}, "horizontalAlignment": "CENTER", "textFormat": {"bold": True, "fontSize": 16, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}})

    # Общий итог
    ws.update(values=[
        ["ОБЩИЙ ИТОГ ЗА 2026 ГОД", "СУММА (руб)"],
        ["Выручка", data['total_revenue']],
        ["Себестоимость (COGS)", data['total_cogs']],
        ["Расходы Ozon", data['total_exp']],
        ["ЧИСТАЯ ПРИБЫЛЬ", data['total_profit']]
    ], range_name="A3")
    ws.format("A3:B7", {"textFormat": {"bold": True}})
    ws.format("B4:B7", {"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}})
    ws.format("A7:B7", {"backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}})

    # Единая таблица
    row_start = 9
    header = ["Артикул", "SKU", "Выручка", "Себестоимость", "Расходы Ozon", "Прибыль", "Мин. цена", "Маржа, %", "Статус"]
    ws.update(values=[header], range_name=f"A{row_start}")
    ws.format(f"A{row_start}:I{row_start}", {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}})

    rows_data = []
    for i in data['items']:
        rows_data.append([
            i['offer_id'] or "",
            i['sku'],
            round(i['revenue'], 2),
            round(i['cogs'], 2),
            round(i['exp'], 2),
            round(i['profit'], 2),
            round(i['min_price'], 2),
            round(i['margin'], 1),
            i['status']
        ])

    if rows_data:
        ws.update(values=rows_data, range_name=f"A{row_start+1}")
        # Форматирование чисел
        ws.format(f"C{row_start+1}:G{row_start+len(rows_data)}", {"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}})
        ws.format(f"H{row_start+1}:H{row_start+len(rows_data)}", {"numberFormat": {"type": "NUMBER", "pattern": "0.0"}})

    # Ширина колонок
    sh.batch_update({
        "requests": [
            {"updateDimensionProperties": {"range": {"sheetId": ws.id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1}, "properties": {"pixelSize": 150}, "fields": "pixelSize"}},
            {"updateDimensionProperties": {"range": {"sheetId": ws.id, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 2}, "properties": {"pixelSize": 120}, "fields": "pixelSize"}},
            {"updateDimensionProperties": {"range": {"sheetId": ws.id, "dimension": "COLUMNS", "startIndex": 2, "endIndex": 9}, "properties": {"pixelSize": 100}, "fields": "pixelSize"}}
        ]
    })

    print(f"Лист 'Юнит-сводка' обновлен. Общая прибыль: {data['total_profit']:,.0f} руб. SKU: {len(data['items'])}")

if __name__ == '__main__':
    main()

