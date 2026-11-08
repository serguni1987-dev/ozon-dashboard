import gspread
from google.oauth2.service_account import Credentials
from unitka import config

creds = Credentials.from_service_account_file(
    str(config.CREDENTIALS),
    scopes=["https://www.googleapis.com/auth/spreadsheets"])
ws = gspread.authorize(creds).open_by_key(config.SHEET_ID).worksheet("Юнит экономика")
headers = ws.row_values(1)
print(f"Всего колонок: {len(headers)}")
print("\nПодозрительные заголовки (с '%%', 'на ед. на ед.'):")
bad = False
for i, h in enumerate(headers, 1):
    if "%%" in h or "на ед. на ед." in h.lower() or h.count("%") >= 2:
        col = ""
        n = i
        while n > 0:
            n, r = divmod(n - 1, 26)
            col = chr(65 + r) + col
        print(f"  {col}: {h!r}")
        bad = True
if not bad:
    print("  — чисто!")