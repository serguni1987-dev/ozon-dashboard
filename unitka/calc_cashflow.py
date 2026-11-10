import os
import gspread
from google.oauth2.service_account import Credentials
from .db import connect
from . import settings

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRED = os.path.join(APP_DIR, "app", "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SHEET_ID = "1Or2Gak6ihm00rM7ZNF4YvGcEPi6ULLadKIgBjnQZ6q0"
MONTHS = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]

def get_start_balance(sh):
    """Остаток денег на 1 января (НАСТРОЙКИ, подпись «Остаток на счёте на 1 января»).
    Не задан → None: тогда показываем накопленный поток, а не выдуманный остаток.

    Раньше сюда подставлялся ТЕКУЩИЙ остаток на счёте, и к нему прибавлялись выплаты
    за весь год — «остаток на конец» получался завышенным на сумму всех выплат."""
    grid = settings.read_grid(sh)
    for row in grid:
        if len(row) >= 2 and settings._norm(row[0]).startswith("остаток на счете на 1 января"):
            return settings.to_float(row[1])
    return None


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
    """Расходы по месяцам: блок «РАСХОДЫ ПО МЕСЯЦАМ» листа НАСТРОЙКИ, иначе старый лист «ДДС Ввод»."""
    block = settings.outflows(sh)
    if block is not None:
        return {m: rec["total"] for m, rec in block.items()}
    outflows = {}
    try:
        ws = sh.worksheet("ДДС Ввод")
        vals = ws.get_all_values()
        # Ожидаем структуру: A=Месяц(число), B=Закупки, C=Налоги, D=Личные, E=Прочее
        for row in vals[1:]:
            if len(row) >= 5 and row[0].isdigit():
                total = sum(settings.to_float(x) or 0.0 for x in row[1:5])
                outflows[int(row[0])] = total
    except gspread.WorksheetNotFound:
        print("Блок «РАСХОДЫ ПО МЕСЯЦАМ» на листе НАСТРОЙКИ не найден — расходы считаются нулевыми.")
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
    from datetime import date
    today = date.today()
    cash_now = settings.manual_inputs(sh)["cash"]
    opening_known = start_balance is not None
    row_inflow = ["Приход (выплаты Ozon)"]
    row_outflow = ["Расход (НАСТРОЙКИ → «Расходы по месяцам»)"]
    row_net = ["Чистый поток (приход − расход)"]
    row_balance = ["Остаток на конец месяца (расчёт)" if opening_known else "Накопленный поток с начала года"]

    current_balance = start_balance or 0.0
    year_inflow = 0
    year_outflow = 0
    balance_today = current_balance

    for m in range(1, 13):
        inf = inflows.get(m, 0.0)
        out = outflows.get(m, 0.0)
        net = inf - out
        current_balance += net
        year_inflow += inf
        year_outflow += out
        future = year > today.year or (year == today.year and m > today.month)
        row_inflow.append(inf)
        row_outflow.append(-out)  # минус для наглядности
        row_net.append(net)
        row_balance.append("" if future else current_balance)
        if not future:
            balance_today = current_balance

    row_inflow.append(year_inflow)
    row_outflow.append(-year_outflow)
    row_net.append(year_inflow - year_outflow)
    row_balance.append(balance_today)

    # Контроль: расчётный остаток против фактического на счёте
    gap = balance_today - cash_now
    if opening_known:
        check_label = "Расхождение: расчётный остаток − факт на счёте (расходы, не внесённые в НАСТРОЙКИ)"
    else:
        check_label = ("Ушло со счёта и не разнесено: выплаты Ozon − внесённые расходы − деньги на счёте сейчас "
                       "(для точного контроля впишите на листе НАСТРОЙКИ остаток на 1 января и расходы по месяцам)")
    tail = [
        [],
        ["КОНТРОЛЬ", "₽"],
        ["Остаток на счёте на 1 января (НАСТРОЙКИ)", start_balance if opening_known else "не задан"],
        ["Деньги на счёте сейчас — факт (НАСТРОЙКИ)", cash_now],
        [check_label, gap],
    ]
    if year_outflow == 0:
        tail.append(["⚠ Расходы не внесены: строка «Расход» пустая, поэтому поток показывает только выплаты Ozon, а не движение денег.", ""])

    ws.update(values=[row_inflow, row_outflow, row_net, row_balance] + tail, range_name="A4")

    # Форматирование
    ws.format("B4:N7", {"numberFormat": {"type": "NUMBER", "pattern": "#,##0.00"}})
    ws.format("B10:B12", {"numberFormat": {"type": "NUMBER", "pattern": "#,##0.00"}})
    ws.format("A4:N13", {"horizontalAlignment": "LEFT"})
    ws.format("A6:N6", {"textFormat": {"bold": True}})
    ws.format("A7:N7", {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}})
    ws.format("A9:B9", {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}})

    opening_txt = f"{start_balance:,.2f}" if opening_known else "не задан"
    print(f"Лист «ДДС» обновлен. Остаток на 1 января: {opening_txt} | расчёт на сегодня: {balance_today:,.2f} | факт на счёте: {cash_now:,.2f}")

if __name__ == '__main__':
    main()