import os
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from .db import connect
from .finance_core import ozon_pnl, year_range, receivables as calc_receivables, inventory_value
from . import settings

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRED = os.path.join(APP_DIR, "app", "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
from .config import SHEET_ID  # ID таблицы: app\.env → PULT_SHEET_ID

def get_manual_inputs(sh):
    """Деньги на счёте и кредиторка — лист НАСТРОЙКИ (unitka.settings)."""
    m = settings.manual_inputs(sh)
    return m["cash"], m["ap"]

def build(sh):
    year = 2026
    today = datetime.now()
    start_year = datetime(year, 1, 1)
    days_passed = (today - start_year).days
    if days_passed == 0: days_passed = 1

    conn = connect()
    cur = conn.cursor()

    # 1–2. Выручка и себестоимость YTD, расходы Ozon — единая формула finance_core (с комиссией)
    p = ozon_pnl(cur, *year_range(year))
    revenue = p["income"]          # валовые доходы (цена + баллы + партнёры)
    bonus = coinv = 0.0            # уже внутри revenue
    cogs = p["cogs"]
    ozon_expenses = p["ozon_total"]

    # 3. Текущий запас (Inventory) — как в Балансе
    inventory = inventory_value(cur)

    # 4. Дебиторка — фактический баланс Ozon
    receivables = calc_receivables(cur)

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

    _r = lambda v: round(float(v), 2)
    revenue, cogs, inventory, receivables, cash, ap = map(_r, (revenue, cogs, inventory, receivables, cash, ap))
    total_capital, net_profit, dio, dso, dpo, ccc, roi, turnover = map(_r, (total_capital, net_profit, dio, dso, dpo, ccc, roi, turnover))
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
        ["Деньги на счету", data['cash'], "Лист НАСТРОЙКИ"],
        ["ИТОГО КАПИТАЛ", data['total_capital'], "Товар + Дебиторка + Деньги"],
        ["", "", ""],
        ["ФИНАНСОВЫЙ ЦИКЛ (CCC)", "", ""],
        ["Дни запаса (DIO)", data['dio'], "Сколько дней продается товар"],
        ["Дни дебиторки (DSO)", data['dso'], "Сколько дней Ozon держит деньги"],
        ["Дни кредиторки (DPO)", data['dpo'], "Сколько дней мы должны поставщикам"],
        ["CCC (DIO + DSO - DPO)", data['ccc'], "Чем меньше, тем лучше"],
        ["", "", ""],
        ["ЭФФЕКТИВНОСТЬ", "", ""],
        ["Валовая прибыль (Доходы − все расходы Ozon, вкл. комиссию − COGS)", data['net_profit'], "Сверено с P&L"],
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