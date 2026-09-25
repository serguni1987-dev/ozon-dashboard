# fix_ref_rows.py — строки 3-6 делаем обычным тёмным текстом (не серым italic).
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

DARK = {"red": 0, "green": 0, "blue": 0}
BORDER = {"red": 0.75, "green": 0.75, "blue": 0.75}

reqs = []
# Строки 3-6 — обычный чёрный, без italic
for r in (3, 4, 5, 6):
    reqs.append({"repeatCell": {
        "range": {"sheetId": sid,
                  "startRowIndex": r-1, "endRowIndex": r,
                  "startColumnIndex": 0, "endColumnIndex": 1},
        "cell": {"userEnteredFormat": {
            "textFormat": {
                "foregroundColor": DARK,
                "italic": False,
                "bold": False,
                "fontSize": 11,
            },
        }},
        "fields": "userEnteredFormat.textFormat"}})

# Плюс — тонкая граница снизу блока (как в образце)
reqs.append({"updateBorders": {
    "range": {"sheetId": sid,
              "startRowIndex": 5, "endRowIndex": 6,
              "startColumnIndex": 0, "endColumnIndex": 19},
    "bottom": {"style": "SOLID", "color": BORDER}}})

sh.batch_update({"requests": reqs})
print(f"[OK] Строки 3-6 перекрашены ({len(reqs)} запросов)")
