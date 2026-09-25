import gspread, re
from google.oauth2.service_account import Credentials

_src = open("sheets_sync.py", encoding="utf-8").read()
SHEET_ID = re.search(r'SHEET_ID\s*=\s*"([^"]+)"', _src).group(1)

scopes = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
client = gspread.authorize(creds)
sh = client.open_by_key(SHEET_ID)
ws = sh.worksheet("P&L")

# Читаем строки 1-4, все колонки
print("Проверка позиций:")
print("Заголовки (строка 1):", ws.get("A1:T1")[0])
print("Заказы (строка 3):    ", ws.get("A3:T3")[0])
print("Доходы (строка 8):    ", ws.get("A8:T8")[0])
