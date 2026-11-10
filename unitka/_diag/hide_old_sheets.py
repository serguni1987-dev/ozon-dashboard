import gspread
from google.oauth2.service_account import Credentials
from unitka import config

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
CRED = str(config.CREDENTIALS)
SHEET_ID = config.SHEET_ID

OLD_SHEETS = [
    "СЕГОДНЯ", "ДЕЛАЙ", "ЦЕНЫ", "ЗАМОРОЗКА", 
    "ДЕНЬГИ", "РЕЗУЛЬТАТ", "ВВОД", "КАПИТАЛ", "ФАКТ"
]

def main():
    creds = Credentials.from_service_account_file(CRED, scopes=SCOPES)
    client = gspread.authorize(creds)
    sh = client.open_by_key(SHEET_ID)
    
    print("=== Скрытие старых листов ===")
    for title in OLD_SHEETS:
        try:
            ws = sh.worksheet(title)
            # Скрываем лист
            sh.batch_update({
                "requests": [{
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": ws.id,
                            "hidden": True
                        },
                        "fields": "hidden"
                    }
                }]
            })
            print(f"  [OK] Скрыт: {title}")
        except gspread.WorksheetNotFound:
            print(f"  [-] Не найден (пропущен): {title}")
        except Exception as e:
            print(f"  [!] Ошибка при скрытии {title}: {e}")
            
    print("\nГотово. Старые листы скрыты (данные сохранены).")

if __name__ == "__main__":
    main()