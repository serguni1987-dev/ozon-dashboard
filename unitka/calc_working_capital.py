import os
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from .db import connect

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRED = os.path.join(APP_DIR, "app", "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SHEET_ID = "1Or2Gak6ihm00rM7ZNF4YvGcEPi6ULLadKIgBjnQZ6q0"

def get_manual_inputs(sh):
    cash, ap = 0.0, 0.0
    try:
        ws = sh.worksheet("Ручной ввод")
        vals = ws.get_all_values()
        for row in vals:
            if len(row) < 2: continue
            key = row[0].strip().lower()
            val_str = row[1].replace(" ", "").replace(",", ".").strip()
            if not val_str or val_str == "значение": continue
            try: val = float(val_str)
            except: continue
            if "деньги" in key or "счет" in key: cash = val
            elif "кредиторка" in key or "поставщик" in key: ap = val
    except Exception:
        pass
    return cash, ap

def build(sh):
    year = 2026
    today = datetime.now()
    start_year = datetime(year, 1, 1)
    days_passed = (today - start_year).days
    if days_passed == 0: days_passed = 1

    conn = connect()
    cur = conn.cursor()

    # 1. Выручка YTD
    cur.execute("SELECT COALESCE(SUM(sale_price), 0) FROM accruals WHERE date LIKE ?", (f"{year}-%",))
    revenue = cur.fetchone()[0]
    cur.execute("SELECT COALESCE(SUM(bonus), 0) FROM accruals WHERE date LIKE ?", (f"{year}-%",))
    bonus = cur.fetchone()[0]
    cur.execute("SELECT COALESCE(SUM(coinvestment), 0) FROM accruals WHERE date LIKE ?", (f"{year}-%",))
    coinv = cur.fetchone()[0]

    # 2. Себестоимость YTD (COGS)
    cur.execute("""
        SELECT SUM(m.quantity * c.cost_price)
        FROM monthly_realization_rows m
        LEFT JOIN (
            SELECT sku, date_from, cost_price FROM product_cost_history
            WHERE (sku, date_from) IN (SELECT sku, MAX(date_from) FROM product_cost_history GROUP BY sku)
        ) c ON m.sku = c.sku
        WHERE m.month LIKE ? AND m.is_return = 0
    """, (f"{year}-%",))
    cogs = cur.fetchone()[0] or 0.0

    # 3. Текущий запас (Inventory)
    cur.execute("SELECT MAX(date) FROM stock_daily")
    last_date = cur.fetchone()[0]
    inventory = 0.0
    if last_date:
        cur.execute("""
            SELECT SUM((s.fbo_present + s.fbs_present) * c.cost_price)
            FROM stock_daily s
            JOIN product_cost_history c ON s.sku = c.sku
            WHERE s.date = ? AND c.date_from = (SELECT MAX(date_from) FROM product_cost_history WHERE sku = s.sku AND date_from <= ?)
        """, (last_date, last_date))
        inventory = cur.fetchone()[0] or 0.0

    # 4. Дебиторка (Receivables)
    cur.execute("SELECT COALESCE(SUM(amount), 0) FROM finance_transactions")
    acc = cur.fetchone()[0]
    cur.execute("SELECT COALESCE(SUM(amount), 0) FROM finance_payouts")
    pay = cur.fetchone()[0]
    receivables = acc - pay

    # 5. Расходы Ozon YTD
    cur.execute("SELECT COALESCE(SUM(ABS(amount)), 0) FROM finance_transactions WHERE type = 'deduction' AND date LIKE ?", (f"{year}-%",))
    ozon_expenses = cur.fetchone()[0]

    conn.close()

    cash, ap = get_manual_inputs(sh)

    # --- РАСЧЕТЫ ---
    # Дни запаса (DIO)
    daily_cogs = cogs / days_passed if cogs > 0 else 0
    dio = inventory / daily_cogs if daily_cogs > 0 else 0

    # Дни дебиторки (DSO)
    daily_revenue = revenue / days_passed if revenue > 0 else 0
    dso = receivables / daily_revenue if daily_revenue > 0 else 0

    # Дни кредиторки (DPO)
    dpo = ap / daily_cogs if daily_cogs > 0 else 0

    # Финансовый цикл (CCC)
    ccc = dio + dso - dpo

    # Капитал и ROI
    total_capital = inventory + receivables + cash
    net_profit = revenue + bonus + coinv - cogs - ozon_expenses
    roi = (net_profit / total_capital * 100) if total_capital > 0 else 0
    turnover = revenue / total_capital if total_capital > 0 else 0

    return {
        'revenue': revenue, 'cogs': cogs, 'inventory': inventory,
        'receivables': receivables, 'cash': cash, 'ap': ap,
        'total_capital': total_capital, 'net_profit': net_profit,
        'dio': dio, 'dso': dso, 'dpo': dpo, 'ccc': ccc,
        'roi': roi, 'turnover': turnover
    }

def main():
    creds = Credentials.from_service_account_file(CRED, scopes=SCOPES)
    client = gspread.authorize(creds)
    sh = client.open_by_key(SHEET_ID)
    
    data = build(sh)

    try:
        ws = sh.worksheet("Оборотный капитал")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title="Оборотный капитал", rows=50, cols=5)
    ws.clear()

    ws.update(values=[["Оборотный капитал и Эффективность (CCC / ROI)"]], range_name="A1")
    try: ws.merge_cells("A1:C1")
    except: pass
    ws.format("A1", {"textFormat": {"bold": True, "fontSize": 14}, "horizontalAlignment": "CENTER"})

    ws.update(values=[
        ["ПОКАЗАТЕЛЬ", "ЗНАЧЕНИЕ", "КОММЕНТАРИЙ"],
        ["Выручка YTD", data['revenue'], "С начала года"],
        ["Себестоимость (COGS) YTD", data['cogs'], "С начала года"],
        ["Товар на складе (сейчас)", data['inventory'], "Остатки * себестоимость"],
        ["Дебиторка Ozon (сейчас)", data['receivables'], "Деньги в Ozon"],
        ["Деньги на счету", data['cash'], "Из Ручного ввода"],
        ["ИТОГО КАПИТАЛ", data['total_capital'], "Товар + Дебиторка + Деньги"],
        ["", "", ""],
        ["ФИНАНСОВЫЙ ЦИКЛ (CCC)", "", ""],
        ["Дни запаса (DIO)", data['dio'], "Сколько дней продается товар"],
        ["Дни дебиторки (DSO)", data['dso'], "Сколько дней Ozon держит деньги"],
        ["Дни кредиторки (DPO)", data['dpo'], "Сколько дней мы должны поставщикам"],
        ["CCC (DIO + DSO - DPO)", data['ccc'], "Чем меньше, тем лучше"],
        ["", "", ""],
        ["ЭФФЕКТИВНОСТЬ", "", ""],
        ["Прибыль (Выручка - COGS - Расходы Ozon)", data['net_profit'], "Упрощенный расчет"],
        ["ROI (Прибыль / Капитал)", f"{data['roi']:.2f}%", "Отдача на вложенный капитал"],
        ["Оборачиваемость капитала", f"{data['turnover']:.2f}", "Выручка на 1 руб. капитала"]
    ], range_name="A3")

    ws.format("B4:B7", {"numberFormat": {"type": "NUMBER", "pattern": "#,##0.00"}})
    ws.format("B11:B15", {"numberFormat": {"type": "NUMBER", "pattern": "#,##0.0"}})
    ws.format("B17:B17", {"numberFormat": {"type": "NUMBER", "pattern": "#,##0.00"}})
    ws.format("A9:A15", {"textFormat": {"bold": True}})
    ws.format("A16:A19", {"textFormat": {"bold": True}})
    
    print(f"Лист «Оборотный капитал» обновлен. CCC: {data['ccc']:.1f} дней. ROI: {data['roi']:.2f}%")

if __name__ == '__main__':
    main()