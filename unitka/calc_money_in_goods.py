import os
import gspread
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials
from .db import connect

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRED = os.path.join(APP_DIR, "app", "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
from .config import SHEET_ID  # ID таблицы: app\.env → PULT_SHEET_ID

def build():
    conn = connect()
    cur = conn.cursor()

    # 1. Берем последнюю дату остатков
    cur.execute("SELECT MAX(date) FROM stock_daily")
    last_date = cur.fetchone()[0]
    if not last_date:
        conn.close()
        return []

    # 2. Считаем продажи за последние 30 дней
    today = datetime.strptime(last_date, '%Y-%m-%d')
    date_30d_ago = (today - timedelta(days=30)).strftime('%Y-%m-%d')

    cur.execute("""
        SELECT sku, SUM(quantity) 
        FROM realization_daily 
        WHERE date >= ? AND is_return = 0
        GROUP BY sku
    """, (date_30d_ago,))
    sales_30d = {row[0]: row[1] for row in cur.fetchall()}

    # 3. Собираем остатки и себестоимость
    cur.execute("""
        SELECT s.sku, 
               (s.fbo_present + s.fbs_present) AS total_qty,
               c.cost_price
        FROM stock_daily s
        LEFT JOIN (
            SELECT sku, cost_price FROM product_cost_history 
            WHERE (sku, date_from) IN (
                SELECT sku, MAX(date_from) FROM product_cost_history WHERE date_from <= ? GROUP BY sku
            )
        ) c ON s.sku = c.sku
        WHERE s.date = ? AND (s.fbo_present + s.fbs_present) > 0
    """, (last_date, last_date))
    
    rows = cur.fetchall()
    conn.close()

    result = []
    for r in rows:
        sku = r['sku']
        qty = r['total_qty']
        cost = r['cost_price'] or 0.0
        stock_value = qty * cost
        
        sold_30d = sales_30d.get(sku, 0)
        daily_sales = sold_30d / 30.0 if sold_30d > 0 else 0
        
        if daily_sales > 0:
            days_of_stock = qty / daily_sales
        else:
            days_of_stock = 999

        if days_of_stock <= 30:
            status = "🟢 Ходовой"
        elif days_of_stock <= 60:
            status = "🟡 Избыток"
        else:
            status = "🔴 Неликвид"

        result.append({
            'sku': sku,
            'qty': qty,
            'cost': cost,
            'stock_value': stock_value,
            'sold_30d': sold_30d,
            'days': days_of_stock,
            'status': status
        })

    result.sort(key=lambda x: x['stock_value'], reverse=True)
    return result

def main():
    data = build()
    if not data:
        print("Нет данных по остаткам. Запустите python -m unitka.load_stocks")
        return

    creds = Credentials.from_service_account_file(CRED, scopes=SCOPES)
    client = gspread.authorize(creds)
    sh = client.open_by_key(SHEET_ID)

    try:
        ws = sh.worksheet("Деньги в товаре")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title="Деньги в товаре", rows=1000, cols=7)
    ws.clear()

    ws.update(values=[["Деньги в товаре (Замороженный капитал)"]], range_name="A1")
    try: ws.merge_cells("A1:G1")
    except: pass
    ws.format("A1", {"textFormat": {"bold": True, "fontSize": 14}, "horizontalAlignment": "CENTER"})

    header = ["SKU", "Остаток (шт)", "Себестоимость", "Сумма (руб)", "Продажи за 30 дн", "Дней запаса", "Статус"]
    ws.update(values=[header], range_name="A3")
    ws.format("A3:G3", {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}})

    out_data = []
    for r in data:
        days_val = r['days'] if r['days'] < 999 else "беск."
        out_data.append([r['sku'], r['qty'], r['cost'], r['stock_value'], r['sold_30d'], days_val, r['status']])
    
    if out_data:
        ws.update(values=out_data, range_name="A4")
        ws.format(f"C4:D{3+len(out_data)}", {"numberFormat": {"type": "NUMBER", "pattern": "#,##0.00"}})
        ws.format(f"F4:F{3+len(out_data)}", {"numberFormat": {"type": "NUMBER", "pattern": "0"}})
        ws.format(f"G4:G{3+len(out_data)}", {"textFormat": {"bold": True}})
        
    print(f"Лист 'Деньги в товаре' обновлен. Всего SKU: {len(out_data)}")

if __name__ == '__main__':
    main()
