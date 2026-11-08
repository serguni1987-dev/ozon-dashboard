import os
import gspread
from google.oauth2.service_account import Credentials
from .db import connect

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRED = os.path.join(APP_DIR, "app", "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SHEET_ID = "1Or2Gak6ihm00rM7ZNF4YvGcEPi6ULLadKIgBjnQZ6q0"
TAX_RATE = 0.07

def get_manual_inputs(sh):
    cash, ap, tax_paid = 0.0, 0.0, 0.0
    try:
        ws = sh.worksheet("Ручной ввод")
        vals = ws.get_all_values()
        for row in vals:
            if len(row) < 2:
                continue
            key = row[0].strip().lower()
            val_str = row[1].replace(" ", "").replace(",", ".").strip()
            
            if not val_str or val_str == "значение":
                continue
                
            try:
                val = float(val_str)
            except ValueError:
                continue

            if "деньги" in key or "счет" in key:
                cash = val
            elif "кредиторка" in key or "поставщик" in key:
                ap = val
            elif "налог" in key or "уплачено" in key:
                tax_paid = val
                
    except Exception as e:
        print(f"Ошибка чтения Ручной ввод: {e}")
    return cash, ap, tax_paid

def build(tax_paid):
    conn = connect()
    cur = conn.cursor()
    
    cur.execute("SELECT MAX(date) FROM stock_daily")
    last_date = cur.fetchone()[0]
    
    inventory = 0.0
    if last_date:
        cur.execute("""
            SELECT SUM((s.fbo_present + s.fbs_present) * c.cost_price)
            FROM stock_daily s
            JOIN product_cost_history c ON s.sku = c.sku
            WHERE s.date = ? 
              AND c.date_from = (SELECT MAX(date_from) FROM product_cost_history WHERE sku = s.sku AND date_from <= ?)
        """, (last_date, last_date))
        inventory = cur.fetchone()[0] or 0.0

    cur.execute("SELECT COALESCE(SUM(amount), 0) FROM finance_transactions")
    acc = cur.fetchone()[0]
    cur.execute("SELECT COALESCE(SUM(amount), 0) FROM finance_payouts")
    pay = cur.fetchone()[0]
    receivables = acc - pay

    cur.execute("SELECT COALESCE(SUM(sale_price), 0) AS rev, COALESCE(SUM(bonus), 0) AS bonus FROM accruals WHERE date LIKE '2026-%'")
    row = cur.fetchone()
    revenue_ytd = row[0]
    bonus_ytd = row[1]
    tax_base = revenue_ytd - bonus_ytd
    tax_total = tax_base * TAX_RATE
    tax_to_pay = max(0, tax_total - tax_paid)

    conn.close()
    return inventory, receivables, tax_to_pay

def main():
    creds = Credentials.from_service_account_file(CRED, scopes=SCOPES)
    client = gspread.authorize(creds)
    sh = client.open_by_key(SHEET_ID)
    
    cash, ap, tax_paid = get_manual_inputs(sh)
    inventory, receivables, tax_to_pay = build(tax_paid)
    
    assets = inventory + receivables + cash
    liabilities = tax_to_pay + ap
    equity = assets - liabilities

    try:
        ws = sh.worksheet("Баланс")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title="Баланс", rows=50, cols=5)
    
    ws.clear()

    ws.update(values=[["Управленческий баланс на сегодня"]], range_name="A1")
    
    # Безопасное объединение ячеек: если не получится, просто пропускаем
    try:
        ws.merge_cells("A1:B1")
    except Exception as e:
        print(f"Предупреждение: не удалось объединить ячейки A1:B1 (это не критично): {e}")
    
    ws.update(values=[
        ["АКТИВЫ", "Сумма"],
        ["Товар на складах (остатки * себестоимость)", inventory],
        ["Дебиторка Ozon", receivables],
        ["Деньги на расчетном счете", cash],
        ["ИТОГО АКТИВЫ", assets],
        ["", ""],
        ["ПАССИВЫ", "Сумма"],
        ["Налоги к уплате (УСН 7%)", tax_to_pay],
        ["Кредиторка поставщикам", ap],
        ["ИТОГО ПАССИВЫ", liabilities],
        ["", ""],
        ["СОБСТВЕННЫЙ КАПИТАЛ", equity]
    ], range_name="A3")

    ws.format("B4:B6", {"numberFormat": {"type": "NUMBER", "pattern": "#,##0.00"}})
    ws.format("B8:B10", {"numberFormat": {"type": "NUMBER", "pattern": "#,##0.00"}})
    ws.format("A12:B12", {"textFormat": {"bold": True, "fontSize": 12}})
    print(f"Баланс обновлен. Товар: {inventory:,.2f} | Дебиторка: {receivables:,.2f} | Капитал: {equity:,.2f}")

if __name__ == '__main__':
    main()