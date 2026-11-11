import os
import gspread
from google.oauth2.service_account import Credentials
from .db import connect
from datetime import datetime
from .finance_core import ozon_pnl, year_range, tax_settings, DEFAULT_TAX_RATE_PCT, DEFAULT_CONTRIB, REGIME_DR, REGIME_INCOME, parse_regime

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRED = os.path.join(APP_DIR, "app", "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
from .config import SHEET_ID  # ID таблицы: app\.env → PULT_SHEET_ID

# Константы для 2026 года
FIXED_IP_CONTRIB = DEFAULT_CONTRIB  # взносы ИП по умолчанию; фактическое значение — НАСТРОЙКИ!B5
LIMIT_300K = 300000.0

def build(year, rate_pct=None, regime=None, contrib=None):
    """Налоги за год по настройкам листа НАСТРОЙКИ.
    rate_pct — ставка УСН, %; regime — «Д-Р» (доходы − расходы) или «Доходы»; contrib — взносы ИП за год."""
    rate_pct = float(rate_pct) if rate_pct else DEFAULT_TAX_RATE_PCT
    regime = parse_regime(regime)
    fixed_contrib = float(contrib) if contrib is not None else FIXED_IP_CONTRIB
    conn = connect()
    cur = conn.cursor()
    p = ozon_pnl(cur, *year_range(year))
    conn.close()

    income = p["income"]                 # валовые доходы (цена + баллы + партнёры)
    commission = p["commission"]         # вознаграждение Ozon — раньше терялось
    services = p["ozon_total"] - commission   # логистика, реклама, эквайринг, корректировки
    ozon_expenses = p["ozon_total"]      # всё, что удержал Ozon
    cogs = p["cogs"]

    base_before_contrib = income - ozon_expenses - cogs
    if regime == REGIME_DR:
        # УСН Д−Р: взносы ИП — расход. 1 % с превышения — от (доходы − расходы) > 300 000.
        variable_contrib = max(0.0, (base_before_contrib - LIMIT_300K) * 0.01)
        total_contrib = fixed_contrib + variable_contrib
        total_expenses = ozon_expenses + cogs + total_contrib
        tax_base = income - total_expenses
        tax_rate = max(0.0, tax_base) * rate_pct / 100.0
        min_tax = income * 0.01                       # минимальный налог 1 % от доходов
        tax_to_pay = max(tax_rate, min_tax)
        contrib_deduction = 0.0
    else:
        # УСН «доходы»: база — все доходы; расходы не учитываются; 1 % с превышения — от доходов.
        # ИП без работников уменьшает налог на уплаченные взносы вплоть до нуля.
        variable_contrib = max(0.0, (income - LIMIT_300K) * 0.01)
        total_contrib = fixed_contrib + variable_contrib
        total_expenses = ozon_expenses + cogs + total_contrib   # справочно, для P&L
        tax_base = income
        tax_rate = income * rate_pct / 100.0
        min_tax = 0.0
        contrib_deduction = min(tax_rate, total_contrib)
        tax_to_pay = tax_rate - contrib_deduction

    return {
        'rate_pct': rate_pct,
        'regime': regime,
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
        'contrib_deduction': contrib_deduction,
        'tax_to_pay': tax_to_pay,
        'is_loss': base_before_contrib - fixed_contrib < 0,
        'fixed_contrib': fixed_contrib,
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
    print(f"Режим: УСН {data['regime']} {r:.0f}%")
    print(f"Налоговая база                {data['tax_base']:>14,.2f}  {'УБЫТОК' if data['is_loss'] else ''}")
    print(f"Налог {r:.0f}%                      {data['tax_rate']:>14,.2f}")
    print(f"Минимальный 1%                {data['min_tax']:>14,.2f}")
    print(f"Вычет взносов                 {data['contrib_deduction']:>14,.2f}")
    print(f"К УПЛАТЕ                      {data['tax_to_pay']:>14,.2f}")


def main():
    import sys
    year = 2026
    if "--local" in sys.argv:
        _print_local(build(year))   # без таблицы — настройки по умолчанию (5 %, Д-Р, 57 390)
        return

    creds = Credentials.from_service_account_file(CRED, scopes=SCOPES)
    client = gspread.authorize(creds)
    sh = client.open_by_key(SHEET_ID)
    data = build(year, **tax_settings(sh))
    r = data['rate_pct']
    dr = data['regime'] == REGIME_DR
    regime_title = "доходы − расходы" if dr else "доходы"
    
    try:
        ws = sh.worksheet("Налоги")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title="Налоги", rows=100, cols=5)
        
    ws.clear()
    
    # Заголовок
    ws.update(values=[[f"Налоги и календарь платежей за {year} год (УСН «{regime_title}» {r:.0f}%) — режим и ставка из листа НАСТРОЙКИ"]], range_name="A1")
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
        ["Страховые взносы ИП" + (" (входят в расходы при УСН Д−Р)" if dr else " (справочно; при УСН «доходы» уменьшают налог)"), data['total_contrib']],
        ["ИТОГО РАСХОДЫ" if dr else "ИТОГО РАСХОДЫ (справочно, в базу не входят)", data['total_expenses']],
        ["Налоговая база (Доходы − Расходы)" + ("  ← УБЫТОК" if data['is_loss'] else "") if dr else "Налоговая база (все доходы)", data['tax_base']],
        [f"Налог УСН {r:.0f}%", data['tax_rate']],
        ["Минимальный налог 1% от доходов" if dr else "Вычет уплаченных взносов ИП (до 100% налога)", data['min_tax'] if dr else -data['contrib_deduction']],
        [f"НАЛОГ К УПЛАТЕ (максимум из {r:.0f}% и 1%)" if dr else "НАЛОГ К УПЛАТЕ (налог − взносы)", data['tax_to_pay']],
        ["", ""],
        ["Страховые взносы ИП (фиксированные)", data['fixed_contrib']],
        ["Страховые взносы ИП (1% с превышения 300 000" + (" по базе Д−Р)" if dr else " по доходам)"), data['variable_contrib']],
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
        ["28.12.2026", "Фиксированные взносы ИП (можно разбить по кварталам)", data['fixed_contrib']],
        ["01.07.2027", "Страховые взносы ИП (1% с превышения 300 000 по базе Д−Р)", data['variable_contrib']]
    ], range_name="A21")
    
    ws.format("C22:C27", {"numberFormat": {"type": "NUMBER", "pattern": "#,##0.00"}})
    
    print(f"Лист «Налоги» обновлен. Налог к уплате: {data['tax_to_pay']:,.2f} ₽")

if __name__ == '__main__':
    main()