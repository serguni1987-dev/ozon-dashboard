import os
import gspread
from google.oauth2.service_account import Credentials
from .db import connect

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRED = os.path.join(APP_DIR, "app", "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SHEET_ID = "1Or2Gak6ihm00rM7ZNF4YvGcEPi6ULLadKIgBjnQZ6q0"
MONTHS = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]

def get_start_balance(sh):
    """Берет начальный остаток денег из листа Ручной ввод."""
    try:
        ws = sh.worksheet("Ручной ввод")
        vals = ws.get_all_values()
        for row in vals:
            if len(row) >= 2 and ("деньги" in row[0].lower() or "счет" in row[0].lower()):
                try:
                    return float(row[1].replace(" ", "").replace(",", "."))
                except: return 0.0
    except Exception:
        pass
    return 0.0

def get_ozon_inflows(year):
    """Берет выплаты Ozon по месяцам из БД."""
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT strftime('%m', date) AS m, SUM(amount)
        FROM finance_payouts
        WHERE date LIKE ?
        GROUP BY m
    """, (f"{year}-%",))
    inflows = {int(row[0]): row[1] for row in cur.fetchall()}
    conn.close()
    return inflows

def get_manual_outflows(sh):
    """Читает расходы из листа ДДС Ввод."""
    outflows = {}
    try:
        ws = sh.worksheet("ДДС Ввод")
        vals = ws.get_all_values()
        # Ожидаем структуру: A=Месяц(число), B=Закупки, C=Налоги, D=Личные, E=Прочее
        for row in vals[1:]: # Пропускаем заголовок
            if len(row) >= 5 and row[0].isdigit():
                month = int(row[0])
                total = sum(float(x.replace(" ", "").replace(",", ".")) for x in row[1:5] if x)
                outflows[month] = total
    except gspread.WorksheetNotFound:
        # Если листа нет — создаем пустой шаблон
        ws = sh.add_worksheet(title="ДДС Ввод", rows=20, cols=6)
        ws.update(values=[
            ["Месяц (1-12)", "Закупки", "Налоги", "Личные траты", "Прочее", "Итого"],
            *[[str(i), "", "", "", "", ""] for i in range(1, 13)]
        ], range_name="A1")
        print("Создан лист «ДДС Ввод». Впишите туда ваши расходы и запустите снова.")
    except Exception as e:
        print(f"Ошибка чтения ДДС Ввод: {e}")
    return outflows

def main():
    year = 2026
    creds = Credentials.from_service_account_file(CRED, scopes=SCOPES)
    client = gspread.authorize(creds)
    sh = client.open_by_key(SHEET_ID)
    
    start_balance = get_start_balance(sh)
    inflows = get_ozon_inflows(year)
    outflows = get_manual_outflows(sh)
    
    # Подготовка листа ДДС
    try:
        ws = sh.worksheet("ДДС")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title="ДДС", rows=50, cols=16)
    ws.clear()
    
    ws.update(values=[[f"Движение денежных средств (ДДС) за {year} год"]], range_name="A1")
    try: ws.merge_cells("A1:N1")
    except: pass
    ws.format("A1", {"textFormat": {"bold": True, "fontSize": 14}, "horizontalAlignment": "CENTER"})
    
    # Заголовки
    header = ["Показатель"] + MONTHS + ["Год"]
    ws.update(values=[header], range_name="A3")
    
    # Строки данных
    row_inflow = ["Приход (Выплаты Ozon)"]
    row_outflow = ["Расход (Закупки, налоги, личное)"]
    row_net = ["Чистый поток (Приход - Расход)"]
    row_balance = ["Остаток на конец месяца"]
    
    current_balance = start_balance
    year_inflow = 0
    year_outflow = 0
    
    for m in range(1, 13):
        inf = inflows.get(m, 0.0)
        out = outflows.get(m, 0.0)
        net = inf - out
        current_balance += net
        
        year_inflow += inf
        year_outflow += out
        
        row_inflow.append(inf)
        row_outflow.append(-out) # Минус для красоты
        row_net.append(net)
        row_balance.append(current_balance)
        
    row_inflow.append(year_inflow)
    row_outflow.append(-year_outflow)
    row_net.append(year_inflow - year_outflow)
    row_balance.append(current_balance) # На конец года
    
    ws.update(values=[row_inflow, row_outflow, row_net, row_balance], range_name="A4")
    
    # Форматирование
    ws.format("B4:N7", {"numberFormat": {"type": "NUMBER", "pattern": "#,##0.00"}})
    ws.format("A4:N7", {"horizontalAlignment": "LEFT"})
    ws.format("A6:N6", {"textFormat": {"bold": True}}) # Чистый поток
    ws.format("A7:N7", {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}}) # Остаток
    
    print(f"Лист «ДДС» обновлен. Начальный остаток: {start_balance:,.2f} | Итоговый: {current_balance:,.2f}")

if __name__ == '__main__':
    main()