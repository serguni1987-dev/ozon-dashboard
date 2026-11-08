import os
import gspread
from google.oauth2.service_account import Credentials
from .db import connect

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRED = os.path.join(APP_DIR, "app", "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SHEET_ID = "1Or2Gak6ihm00rM7ZNF4YvGcEPi6ULLadKIgBjnQZ6q0"

HEADER = ['Дата', 'Тип', 'Операция', 'Сумма', 'Номер отправления', 'SKU']

def build(date_from, date_to):
    conn = connect()
    cur = conn.cursor()
    
    # 1. Дебиторка = последний end_balance из balance_periods
    cur.execute("SELECT end_balance, period_end FROM balance_periods WHERE period_end <= ? ORDER BY period_end DESC LIMIT 1", (date_to,))
    row = cur.fetchone()
    if row:
        total_accrued = row[0]
        actual_period = row[1]
    else:
        total_accrued = 0
        actual_period = "нет данных"

    # 2. Выплачено = сумма всех выплат в finance_payouts
    cur.execute("SELECT COALESCE(SUM(amount), 0) FROM finance_payouts WHERE date <= ?", (date_to,))
    paid = cur.fetchone()[0]
    
    # Дебиторка — это и есть end_balance (Ozon уже вычел все выплаты)
    receivables = total_accrued

    # 3. Транзакции (начисления) за период
    cur.execute("SELECT date, type, operation_type, amount, posting_number, sku FROM finance_transactions WHERE date >= ? AND date <= ? ORDER BY date, operation_id", (date_from, date_to))
    trans_rows = cur.fetchall()

    # 4. Выплаты за период
    cur.execute("SELECT date, amount, period_from, period_to, status FROM finance_payouts WHERE date >= ? AND date <= ? ORDER BY date", (date_from, date_to))
    payout_rows = cur.fetchall()
    
    conn.close()
    return {'accrued': total_accrued, 'paid': paid, 'receivables': receivables, 'actual_period': actual_period}, trans_rows, payout_rows

def main(date_from, date_to, local=False):
    summary, trans, payouts = build(date_from, date_to)
    
    if local:
        print('=== СВОДКА ===')
        print(f"Дебиторка (баланс Ozon) на {summary['actual_period']}: {summary['accrued']:,.2f} руб.")
        print(f"Всего выплачено (нарастающим итогом): {summary['paid']:,.2f} руб.")
        print(f"Дебиторка (к получению): {summary['receivables']:,.2f} руб.")
        print(f"Транзакций за период: {len(trans)} | Выплат за период: {len(payouts)}")
        return

    creds = Credentials.from_service_account_file(CRED, scopes=SCOPES)
    client = gspread.authorize(creds)
    # Увеличиваем таймаут
    client.set_timeout(180)
    sh = client.open_by_key(SHEET_ID)
    
    try:
        ws = sh.worksheet('Дебиторка / Выплаты')
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title='Дебиторка / Выплаты', rows=2000, cols=10)
        
    ws.clear()

    # Заголовок
    ws.update(values=[['Дебиторка Ozon / Выплаты']], range_name='A1')
    ws.merge_cells('A1:F1')
    ws.format('A1', {'backgroundColor': {'red': 0.18, 'green': 0.33, 'blue': 0.59}, 'horizontalAlignment': 'CENTER', 'textFormat': {'bold': True, 'fontSize': 14, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}}})

    # Сводка
    ws.update(values=[
        ['Показатель', 'Сумма'],
        [f'Дебиторка (баланс Ozon) на {summary["actual_period"]}', summary['accrued']],
        ['Всего выплачено (нарастающим итогом)', summary['paid']],
        ['Дебиторка (к получению)', summary['receivables']]
    ], range_name='A3')
    ws.format('B4:B6', {'numberFormat': {'type': 'NUMBER', 'pattern': '#,##0.00'}})

    # Транзакции: выводим только последние 300 (полные данные всегда в БД)
    row_start = 8
    ws.update(values=[HEADER], range_name=f'A{row_start}')
    ws.format(f'A{row_start}:F{row_start}', {'textFormat': {'bold': True}, 'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}})
    
    display_trans = trans[-300:] if trans else []
    if display_trans:
        data = [[r[0], r[1], r[2], r[3], r[4], r[5]] for r in display_trans]
        # Разбиваем на куски по 100 строк
        for i in range(0, len(data), 100):
            chunk = data[i:i+100]
            start_row = row_start + 1 + i
            ws.update(values=chunk, range_name=f'A{start_row}')
            print(f'  --> Транзакции: записано {i+len(chunk)} из {len(data)}')
        ws.format(f'D{row_start+1}:D{row_start+len(data)}', {'numberFormat': {'type': 'NUMBER', 'pattern': '#,##0.00'}})

    # Выплаты
    payout_start = row_start + len(display_trans) + 3
    ws.update(values=[['Дата выплаты', 'Сумма', 'Период с', 'Период по', 'Статус']], range_name=f'A{payout_start}')
    ws.format(f'A{payout_start}:E{payout_start}', {'textFormat': {'bold': True}, 'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}})
    
    if payouts:
        payout_data = [[r[0], r[1], r[2], r[3], r[4]] for r in payouts]
        # Выплат обычно немного, но разобьем на всякий случай
        for i in range(0, len(payout_data), 50):
            chunk = payout_data[i:i+50]
            start_row = payout_start + 1 + i
            ws.update(values=chunk, range_name=f'A{start_row}')
        ws.format(f'B{payout_start+1}:B{payout_start+len(payout_data)}', {'numberFormat': {'type': 'NUMBER', 'pattern': '#,##0.00'}})

    print(f'Лист «Дебиторка / Выплаты» обновлён. Транзакций показано: {len(display_trans)} из {len(trans)}, Выплат: {len(payouts)}.')
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--from', dest='date_from', required=True)
    parser.add_argument('--to', dest='date_to', required=True)
    parser.add_argument('--local', action='store_true')
    args = parser.parse_args()
    main(args.date_from, args.date_to, args.local)