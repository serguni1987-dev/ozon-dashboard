import os
import gspread
from google.oauth2.service_account import Credentials
from .db import connect
from datetime import datetime

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRED = os.path.join(APP_DIR, "app", "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SHEET_ID = "1Or2Gak6ihm00rM7ZNF4YvGcEPi6ULLadKIgBjnQZ6q0"

# Константы для 2026 года
FIXED_IP_CONTRIB = 53658.0  # Фиксированные взносы ИП
LIMIT_300K = 300000.0

def build(year):
    conn = connect()
    cur = conn.cursor()
    
    # 1. Доходы (sale_price)
    cur.execute("SELECT COALESCE(SUM(sale_price + bonus + coinvestment), 0) FROM accruals WHERE date LIKE ?", (f"{year}-%",))
    income = cur.fetchone()[0]
    
    # 2. Расходы Ozon (все удержания: комиссии, логистика, реклама)
    cur.execute("SELECT COALESCE(SUM(ABS(amount)), 0) FROM finance_transactions WHERE type = 'deduction' AND date LIKE ?", (f"{year}-%",))
    ozon_expenses = cur.fetchone()[0]
    
    # 3. Себестоимость (COGS) - упрощенный расчет
    # Берем количество из monthly_realization_rows и умножаем на себестоимость на конец месяца
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
    
    # 4. Расчет налоговой базы и налогов
    total_expenses = ozon_expenses + cogs
    tax_base = income - total_expenses
    
    # УСН 15% от прибыли
    tax_15 = max(0, tax_base * 0.15)
    
    # Минимальный налог 1% от доходов
    min_tax = income * 0.01
    
    # К уплате (что больше: 15% или 1%)
    tax_to_pay = max(tax_15, min_tax)
    
    # 5. Страховые взносы ИП
    # Фиксированные + 1% с превышения 300к (считаем от прибыли, так как УСН 15%)
    variable_contrib = max(0, (tax_base - LIMIT_300K) * 0.01)
    total_contrib = FIXED_IP_CONTRIB + variable_contrib
    
    conn.close()
    
    return {
        'income': income,
        'ozon_expenses': ozon_expenses,
        'cogs': cogs,
        'total_expenses': total_expenses,
        'tax_base': tax_base,
        'tax_15': tax_15,
        'min_tax': min_tax,
        'tax_to_pay': tax_to_pay,
        'fixed_contrib': FIXED_IP_CONTRIB,
        'variable_contrib': variable_contrib,
        'total_contrib': total_contrib
    }

def main():
    year = 2026
    data = build(year)
    
    creds = Credentials.from_service_account_file(CRED, scopes=SCOPES)
    client = gspread.authorize(creds)
    sh = client.open_by_key(SHEET_ID)
    
    try:
        ws = sh.worksheet("Налоги")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title="Налоги", rows=100, cols=5)
        
    ws.clear()
    
    # Заголовок
    ws.update(values=[[f"Налоги и календарь платежей за {year} год (УСН 15%)"]], range_name="A1")
    try: ws.merge_cells("A1:E1")
    except: pass
    ws.format("A1", {"textFormat": {"bold": True, "fontSize": 14}, "horizontalAlignment": "CENTER"})

    # Таблица расчета
    ws.update(values=[
        ["Показатель", "Сумма (₽)"],
        ["Доходы (выручка)", data['income']],
        ["Расходы Ozon (комиссии, логистика)", data['ozon_expenses']],
        ["Себестоимость (COGS)", data['cogs']],
        ["ИТОГО РАСХОДЫ", data['total_expenses']],
        ["Налоговая база (Доходы - Расходы)", data['tax_base']],
        ["Налог УСН 15%", data['tax_15']],
        ["Минимальный налог 1%", data['min_tax']],
        ["НАЛОГ К УПЛАТЕ (максимум из 15% и 1%)", data['tax_to_pay']],
        ["", ""],
        ["Страховые взносы ИП (фиксированные)", data['fixed_contrib']],
        ["Страховые взносы ИП (1% с превышения)", data['variable_contrib']],
        ["ИТОГО ВЗНОСЫ ИП", data['total_contrib']]
    ], range_name="A3")
    
    ws.format("B4:B15", {"numberFormat": {"type": "NUMBER", "pattern": "#,##0.00"}})
    ws.format("A9:B9", {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}})
    ws.format("A15:B15", {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}})

    # Календарь платежей
    ws.update(values=[["КАЛЕНДАРЬ ПЛАТЕЖЕЙ"]], range_name="A18")
    ws.format("A18", {"textFormat": {"bold": True, "fontSize": 12}})
    
    ws.update(values=[
        ["Дата", "Назначение платежа", "Сумма"],
        ["28.04.2026", "Аванс УСН за 1 квартал", "Расчет по кварталам"],
        ["28.07.2026", "Аванс УСН за полугодие", "Расчет по кварталам"],
        ["28.10.2026", "Аванс УСН за 9 месяцев", "Расчет по кварталам"],
        ["28.04.2027", "Итоговый налог за год", data['tax_to_pay']],
        ["01.12.2026", "Страховые взносы ИП (1% с превышения)", data['variable_contrib']],
        ["31.12.2026", "Фиксированные взносы ИП (можно разбить по кварталам)", data['fixed_contrib']]
    ], range_name="A19")
    
    ws.format("C20:C25", {"numberFormat": {"type": "NUMBER", "pattern": "#,##0.00"}})
    
    print(f"Лист «Налоги» обновлен. Налог к уплате: {data['tax_to_pay']:,.2f} ₽")

if __name__ == '__main__':
    main()