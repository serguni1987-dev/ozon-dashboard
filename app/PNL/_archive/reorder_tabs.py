"""
reorder_tabs.py — расставляет листы Google Sheets в логичном порядке.
Порядок: ИНСТРУКЦИЯ → СЕГОДНЯ → ДЕЛАЙ → ЦЕНЫ → ЗАМОРОЗКА → ДЕНЬГИ → РЕЗУЛЬТАТ
"""
import gspread
from google.oauth2.service_account import Credentials

SHEET_ID = "1Or2Gak6ihm00rM7ZNF4YvGcEPi6ULLadKIgBjnQZ6q0"
CREDENTIALS = "credentials.json"

ORDER = ["ИНСТРУКЦИЯ", "СЕГОДНЯ", "ДЕЛАЙ", "ЦЕНЫ",
         "ЗАМОРОЗКА", "ДЕНЬГИ", "РЕЗУЛЬТАТ"]


def main():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(CREDENTIALS, scopes=scopes)
    client = gspread.authorize(creds)
    sh = client.open_by_key(SHEET_ID)

    # Текущий порядок
    current = [ws.title for ws in sh.worksheets()]
    print("Текущий порядок:")
    for i, t in enumerate(current):
        print(f"  {i}: {t}")

    # Формируем batch-запросы на перемещение
    requests = []
    for target_index, title in enumerate(ORDER):
        try:
            ws = sh.worksheet(title)
        except gspread.WorksheetNotFound:
            print(f"  [SKIP] {title} — не найден")
            continue
        requests.append({
            "updateSheetProperties": {
                "properties": {"sheetId": ws.id, "index": target_index},
                "fields": "index",
            }
        })

    if requests:
        sh.batch_update({"requests": requests})
        print(f"\n[OK] Отправлено {len(requests)} запросов на перемещение")

    # Проверка
    new_order = [ws.title for ws in sh.worksheets()]
    print("\nНовый порядок:")
    for i, t in enumerate(new_order):
        print(f"  {i}: {t}")


if __name__ == "__main__":
    main()
