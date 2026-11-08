import os
import time
import gspread
from google.oauth2.service_account import Credentials
from .db import connect

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRED = os.path.join(APP_DIR, "app", "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SHEET_ID = "1Or2Gak6ihm00rM7ZNF4YvGcEPi6ULLadKIgBjnQZ6q0"

def build():
    conn = connect()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT month FROM (
            SELECT DISTINCT substr(date, 1, 7) as month FROM finance_transactions
            UNION
            SELECT DISTINCT substr(date, 1, 7) as month FROM finance_payouts
        ) ORDER BY month
    """)
    months = [r[0] for r in cur.fetchall() if r[0]]
    
    if not months:
        return []

    data = []
    cur.execute("SELECT begin_balance FROM balance_periods WHERE period_begin <= ? ORDER BY period_begin ASC LIMIT 1", (months[0] + '-01',))
    row = cur.fetchone()
    current_balance = row[0] if row else 0.0

    for month in months:
        cur.execute("""
            SELECT 
                COALESCE(SUM(CASE WHEN type = 'accrual' THEN amount ELSE 0 END), 0) as accrued,
                COALESCE(SUM(CASE WHEN type = 'deduction' THEN amount ELSE 0 END), 0) as deducted
            FROM finance_transactions
            WHERE substr(date, 1, 7) = ?
        """, (month,))
        acc, ded = cur.fetchone()
        
        cur.execute("SELECT COALESCE(SUM(amount), 0) FROM finance_payouts WHERE substr(date, 1, 7) = ?", (month,))
        paid = cur.fetchone()[0]
        
        current_balance = current_balance + acc + ded - paid
        
        cur.execute("""
            SELECT end_balance, period_end 
            FROM balance_periods 
            WHERE substr(period_end, 1, 7) = ? 
            ORDER BY period_end DESC LIMIT 1
        """, (month,))
        fact_row = cur.fetchone()
        fact_balance = fact_row[0] if fact_row else None
        fact_period = fact_row[1] if fact_row else ""

        data.append({
            'month': month,
            'accrued': acc,
            'deducted': abs(ded),
            'net': acc + ded,
            'paid': paid,
            'balance': current_balance,
            'fact_balance': fact_balance,
            'fact_period': fact_period
        })

    conn.close()
    return data

def connect_to_sheets(retries=5):
    for attempt in range(retries):
        try:
            creds = Credentials.from_service_account_file(CRED, scopes=SCOPES)
            client = gspread.authorize(creds)
            client.set_timeout(180)
            sh = client.open_by_key(SHEET_ID)
            return sh
        except Exception as e:
            print(f"  [!] Ошибка подключения к Google (попытка {attempt+1}/{retries}): {e}")
            if attempt < retries - 1:
                print(f"  --> Ждем 10 секунд и пробуем снова...")
                time.sleep(10)
    raise Exception("Не удалось подключиться к Google Sheets после всех попыток. Проверьте VPN.")

def main(local=False):
    data = build()
    if not data:
        print("Нет данных для сверки.")
        return

    if local:
        print('=== АКТ СВЕРКИ (локально) ===')
        print(f'{"Месяц":<10} {"Начислено":>12} {"Удержано":>12} {"Net":>12} {"Выплачено":>12} {"Баланс":>12} {"Факт Ozon":>12}')
        print('-' * 90)
        for d in data:
            fact = f"{d['fact_balance']:,.2f}" if d['fact_balance'] is not None else "—"
            print(f'{d["month"]:<10} {d["accrued"]:>12,.2f} {d["deducted"]:>12,.2f} {d["net"]:>12,.2f} {d["paid"]:>12,.2f} {d["balance"]:>12,.2f} {fact:>12}')
        return

    print("Подключение к Google Sheets...")
    sh = connect_to_sheets()
    
    try:
        ws = sh.worksheet('Сверка с Ozon')
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title='Сверка с Ozon', rows=100, cols=10)
        
    ws.clear()

    ws.update(values=[['Акт сверки с Ozon по месяцам']], range_name='A1')
    ws.merge_cells('A1:H1')
    ws.format('A1', {'backgroundColor': {'red': 0.18, 'green': 0.33, 'blue': 0.59}, 'horizontalAlignment': 'CENTER', 'textFormat': {'bold': True, 'fontSize': 14, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}}})

    headers = ['Месяц', 'Начислено (Доходы)', 'Удержано (Расходы)', 'Итого начислено (Net)', 'Выплачено', 'Расчетный баланс на конец', 'Факт. баланс Ozon', 'Дата факт. баланса']
    ws.update(values=[headers], range_name='A3')
    ws.format('A3:H3', {'textFormat': {'bold': True}, 'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}})

    rows = []
    for d in data:
        fact_bal = d['fact_balance'] if d['fact_balance'] is not None else ""
        rows.append([
            d['month'], d['accrued'], d['deducted'], d['net'], 
            d['paid'], d['balance'], fact_bal, d['fact_period']
        ])
    
    if rows:
        ws.update(values=rows, range_name='A4')
        end_row = 3 + len(rows)
        ws.format(f'B4:G{end_row}', {'numberFormat': {'type': 'NUMBER', 'pattern': '#,##0.00'}})
        
        for i, d in enumerate(data):
            row_num = 4 + i
            if d['fact_balance'] is not None:
                diff = abs(d['balance'] - d['fact_balance'])
                if diff > 1.0:
                    ws.format(f'F{row_num}:G{row_num}', {'backgroundColor': {'red': 1, 'green': 0.8, 'blue': 0.8}})
                    ws.format(f'F{row_num}:G{row_num}', {'textFormat': {'bold': True, 'foregroundColor': {'red': 0.6, 'green': 0, 'blue': 0}}})

    print(f'Лист «Сверка с Ozon» обновлён. Строк: {len(rows)}.')

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--local', action='store_true', help='Вывод только в консоль без Google Sheets')
    args = parser.parse_args()
    main(args.local)