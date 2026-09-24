# fix_all_subrows.py — все подстроки во всех блоках приводим к одному стилю
# (как у ДОХОДОВ: чёрные, 11pt, не italic, значения в том же шрифте).
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

# (родитель, [подстроки]) — все блоки где родитель = сумма детей
BLOCKS = [
    (8,  [9, 10, 11, 12]),      # ДОХОДЫ
    (16, [17, 18, 19, 20]),     # Озон фулфилмент
    (21, [22, 23]),             # Озон маркетинг
    (33, [34, 35, 36, 37]),     # Операционные расходы
]

reqs = []
for parent, children in BLOCKS:
    for r in [parent] + children:
        # текст (колонка A) — чёрный, 11pt, без italic/bold
        reqs.append({"repeatCell": {
            "range": {"sheetId": sid,
                      "startRowIndex": r-1, "endRowIndex": r,
                      "startColumnIndex": 0, "endColumnIndex": 1},
            "cell": {"userEnteredFormat": {
                "textFormat": {
                    "foregroundColor": BLACK,
                    "italic": False, "bold": False, "fontSize": 11}}},
            "fields": "userEnteredFormat.textFormat"}})
        # значения (B:S) — тот же цвет, тот же размер
        reqs.append({"repeatCell": {
            "range": {"sheetId": sid,
                      "startRowIndex": r-1, "endRowIndex": r,
                      "startColumnIndex": 1, "endColumnIndex": 19},
            "cell": {"userEnteredFormat": {
                "textFormat": {
                    "foregroundColor": BLACK,
                    "italic": False, "bold": False, "fontSize": 11}}},
            "fields": "userEnteredFormat.textFormat"}})

sh.batch_update({"requests": reqs})
print(f"[OK] Обработано блоков: {len(BLOCKS)}, строк: {sum(1+len(c) for _,c in BLOCKS)}")
