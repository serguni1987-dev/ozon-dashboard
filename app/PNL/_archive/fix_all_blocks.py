# fix_all_blocks.py — выравнивает шрифт во всех блоках «родитель+дети».
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

BLACK = {"red": 0, "green": 0, "blue": 0}

# (родитель, [дети])
BLOCKS = [
    (8,  [9, 10, 11, 12]),      # ДОХОДЫ
    (16, [17, 18, 19, 20]),     # Фулфилмент
    (21, [22, 23]),             # Маркетинг
    (33, [34, 35, 36, 37]),     # Операционные
]

reqs = []
for parent, children in BLOCKS:
    for r in [parent] + children:
        reqs.append({"repeatCell": {
            "range": {"sheetId": sid,
                      "startRowIndex": r-1, "endRowIndex": r,
                      "startColumnIndex": 0, "endColumnIndex": 19},
            "cell": {"userEnteredFormat": {
                "textFormat": {
                    "foregroundColor": BLACK,
                    "italic": False,
                    "bold": False,
                    "fontSize": 11,
                },
            }},
            "fields": "userEnteredFormat.textFormat"}})

sh.batch_update({"requests": reqs})
print(f"[OK] Выровнено блоков: {len(BLOCKS)} ({len(reqs)} запросов)")
