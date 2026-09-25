# fix_income_children.py — возвращаем строки 9-12 (Выручка, Баллы, Программы, Компенсации)
# к обычному виду: чёрный, 11pt, без italic. Родитель 8 остаётся bold.
import os, gspread
from google.oauth2.service_account import Credentials
import sync_pnl

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CRED = os.path.join(APP_DIR, "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]

creds = Credentials.from_service_account_file(CRED, scopes=SCOPES)
gc = gspread.authorize(creds)
sh = gc.open_by_key(sync_pnl.SHEET_ID)
ws = sh.worksheet("P&L")
sid = ws.id

BLACK = {"red": 0.0, "green": 0.0, "blue": 0.0}

reqs = []
for r in (9, 10, 11, 12):
    reqs.append({"repeatCell": {
        "range": {"sheetId": sid,
                  "startRowIndex": r-1, "endRowIndex": r,
                  "startColumnIndex": 0, "endColumnIndex": 19},
        "cell": {"userEnteredFormat": {"textFormat": {
            "foregroundColor": BLACK,
            "italic": False, "bold": False, "fontSize": 11}}},
        "fields": "userEnteredFormat.textFormat"}})

sh.batch_update({"requests": reqs})
print("[OK] Строки 9-12 вернули обычный вид")
