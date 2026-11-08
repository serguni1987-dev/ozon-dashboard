import os
import gspread
from google.oauth2.service_account import Credentials
from .db import connect
from datetime import datetime
from .finance_core import ozon_pnl, year_range, tax_rate_pct, DEFAULT_TAX_RATE_PCT

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRED = os.path.join(APP_DIR, "app", "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SHEET_ID = "1Or2Gak6ihm00rM7ZNF4YvGcEPi6ULLadKIgBjnQZ6q0"

# Константы для 2026 года
FIXED_IP_CONTRIB = 53658.0  # Фиксированные взносы ИП
LIMIT_300K = 300000.0

def build(year, rate_pct=None):
    """Налоги за год. rate_pct — ставка УСН «доходы − расходы» в %, по умолчанию из finance_core."""
    rate_pct = float(rate_pct) if rate_pct else DEFAULT_TAX_RATE_PCT
    conn = connect()
    cur = conn.cursor()
    p = ozon_pnl(cur, *year_range(year))
    conn.close()

    income = p["income"]                 # валовые доходы (цена + баллы + партнёры)
    commission = p["commission"]         # вознаграждение Ozon — раньше терялось
    services = p["ozon_total"] - commission   # логистика, реклама, эквайринг, корректировки
    ozon_expenses = p["ozon_total"]      # всё, что удержал Ozon
    cogs = p["cogs"]

    # УСН Д−Р: страховые взносы ИП — тоже расход. Фиксированные — всегда;
    # 1% с превышения считается от (доходы − расходы без взносов) > 300 000.
    base_before_contrib = income - ozon_expenses - cogs
    variable_contrib = max(0.0, (base_before_contrib - LIMIT_300K) * 0.01)
    total_contrib = FIXED_IP_CONTRIB + variable_contrib

    total_expenses = ozon_expenses + cogs + total_contrib
    tax_base = income - total_expenses
    tax_rate = max(0.0, tax_base) * rate_pct / 100.0
    min_tax = income * 0.01                       # минимальный налог 1% от доходов
    tax_to_pay = max(tax_rate, min_tax)

    return {
        'rate_pct': rate_pct,
        'income': income,
        'commission': commission,
        'services': services,
        'ozon_expenses': ozon_expenses,
        'cogs': cogs,
        'cogs_estimated': p["cogs_estimated"],
        'total_expenses': total_expenses,
        'tax_base': tax_base,
        'tax_15': tax_rate,          # имя оставлено для совместимости с calc_dashboard/calc_pulse
        'tax_rate': tax_rate,
        'min_tax': min_tax,
        'tax_to_pay': tax_to_pay,
        'is_loss': tax_base < 0,
        'fixed_contrib': FIXED_IP_CONTRIB,
        'variable_contrib': variable_contrib,
        'total_contrib': total_contrib
    }

def _print_local(data):
    r = data['rate_pct']
    print(f"Доходы (валовые)              {data['income']:>14,.2f}")
    print(f"  Вознаграждение Ozon         {data['commission']:>14,.2f}")
    print(f"  Услуги Ozon и корректировки {data['services']:>14,.2f}")
    print(f"Себестоимость (с возвратами)  {data['cogs']:>14,.2f}{'  (оценка за открытый месяц)' if data['cogs_estimated'] else ''}")
    print(f"Взносы ИП                     {data['total_contrib']:>14,.2f}")
    print(f"Налоговая база                {data['tax_base']:>14,.2f}  {'УБЫТОК' if data['is_loss'] else ''}")
    print(f"Налог {r:.0f}%                      {data['tax_rate']:>14,.2f}")
    print(f"Минимальный 1%                {data['min_tax']:>14,.2f}")
    print(f"К УПЛАТЕ                      {data['tax_to_pay']:>14,.2f}")


def main():
    import sys
    year = 2026
    if "--local" in sys.argv:
        _print_local(build(year))
        return

    creds = Credentials.from_service_account_file(CRED, scopes=SCOPES)
    client = gspread.authorize(creds)
    sh = client.open_by_key(SHEET_ID)
    data = build(year, tax_rate_pct(sh))
    r = data['rate_pct']
    
    try:
        ws = sh.worksheet("Налоги")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title="Налоги", rows=100, cols=5)
        
    ws.clear()
    
    # Заголовок
    ws.update(values=[[f"Налоги и календарь платежей за {year} год (УСН «доходы − расходы» {r:.0f}%)"]], range_name="A1")
    try: ws.merge_cells("A1:E1")
    except: pass
    ws.format("A1", {"textFormat": {"bold": True, "fontSize": 14}, "horizontalAlignment": "CENTER"})

    # Таблица расчета
    ws.update(values=[
        ["Показатель", "Сумма (₽)"],
        ["Доходы (валовые: цена + баллы + партнёры)", data['income']],
        ["Вознаграждение Ozon (комиссия)", data['commission']],
        ["Услуги Ozon (логистика, реклама, эквайринг…)", data['services']],
        ["Себестоимость (COGS, с учётом возвратов)" + (" — оценка за открытый месяц" if data['cogs_estimated'] else ""), data['cogs']],
        ["Страховые взносы ИП (входят в расходы при УСН Д−Р)", data['total_contrib']],
        ["ИТОГО РАСХОДЫ", data['total_expenses']],
        ["Налоговая база (Доходы − Расходы)" + ("  ← УБЫТОК" if data['is_loss'] else ""), data['tax_base']],
        [f"Налог УСН {r:.0f}%", data['tax_rate']],
        ["Минимальный налог 1% от доходов", data['min_tax']],
        [f"НАЛОГ К УПЛАТЕ (максимум из {r:.0f}% и 1%)", data['tax_to_pay']],
        ["", ""],
        ["Страховые взносы ИП (фиксированные)", data['fixed_contrib']],
        ["Страховые взносы ИП (1% с превышения 300 000)", data['variable_contrib']],
        ["ИТОГО ВЗНОСЫ ИП", data['total_contrib']]
    ], range_name="A3")

    ws.format("B4:B17", {"numberFormat": {"type": "NUMBER", "pattern": "#,##0.00"}})
    ws.format("A13:B13", {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}})
    ws.format("A17:B17", {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}})

    # Календарь платежей
    ws.update(values=[["КАЛЕНДАРЬ ПЛАТЕЖЕЙ"]], range_name="A20")
    ws.format("A20", {"textFormat": {"bold": True, "fontSize": 12}})
    
    ws.update(values=[
        ["Дата", "Назначение платежа", "Сумма"],
        ["28.04.2026", "Аванс УСН за 1 квартал", "Расчет по кварталам"],
        ["28.07.2026", "Аванс УСН за полугодие", "Расчет по кварталам"],
        ["28.10.2026", "Аванс УСН за 9 месяцев", "Расчет по кварталам"],
        ["28.04.2027", "Итоговый налог за год", data['tax_to_pay']],
        ["01.12.2026", "Страховые взносы ИП (1% с превышения)", data['variable_contrib']],
        ["31.12.2026", "Фиксированные взносы ИП (можно разбить по кварталам)", data['fixed_contrib']]
    ], range_name="A21")
    
    ws.format("C22:C27", {"numberFormat": {"type": "NUMBER", "pattern": "#,##0.00"}})
    
    print(f"Лист «Налоги» обновлен. Налог к уплате: {data['tax_to_pay']:,.2f} ₽")

if __name__ == '__main__':
    main()