import os
import gspread
from google.oauth2.service_account import Credentials
from .db import connect
from .finance_core import receivables as calc_receivables, inventory_value, tax_settings
from . import settings
from .calc_taxes import build as build_taxes

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRED = os.path.join(APP_DIR, "app", "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SHEET_ID = "1Or2Gak6ihm00rM7ZNF4YvGcEPi6ULLadKIgBjnQZ6q0"

def get_manual_inputs(sh):
    """Деньги на счёте, кредиторка, уплаченные налоги — лист НАСТРОЙКИ (unitka.settings)."""
    m = settings.manual_inputs(sh)
    return m["cash"], m["ap"], m["tax_paid"]

def build(tax_paid, settings=None):
    conn = connect()
    cur = conn.cursor()
    inventory = inventory_value(cur)          # остатки × себестоимость — как в Оборотном капитале и Пульте
    receivables = calc_receivables(cur)       # фактический баланс Ozon
    conn.close()

    # Налог к уплате — из единого расчёта calc_taxes (УСН Д−Р, минимальный 1% при убытке), минус уже уплаченное
    tax_data = build_taxes(2026, **(settings or {}))
    tax_to_pay = max(0.0, tax_data['tax_to_pay'] - tax_paid)
    label = f"УСН Д−Р {tax_data['rate_pct']:.0f}%, минимум 1%" if tax_data['regime'] == 'Д-Р' else f"УСН доходы {tax_data['rate_pct']:.0f}% минус взносы"
    return inventory, receivables, tax_to_pay, label

def main():
    creds = Credentials.from_service_account_file(CRED, scopes=SCOPES)
    client = gspread.authorize(creds)
    sh = client.open_by_key(SHEET_ID)
    
    cash, ap, tax_paid = get_manual_inputs(sh)
    inventory, receivables, tax_to_pay, rate = build(tax_paid, tax_settings(sh))
    
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
        [f"Налоги к уплате ({rate})", tax_to_pay],
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