# fix_parent_child.py — родитель: чёрный bold 11pt; дети: серый italic 10pt.
# Стиль применяется и к тексту (A), и к значениям (B:S).
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
GREY  = {"red": 0.45, "green": 0.45, "blue": 0.45}

# (родитель, [дети])
BLOCKS = [
    (8,  [9, 10, 11, 12]),      # ДОХОДЫ
    (16, [17, 18, 19, 20]),     # Фулфилмент
    (21, [22, 23]),             # Маркетинг
    (33, [34, 35, 36, 37]),     # Операционные
]

reqs = []
for parent, children in BLOCKS:
    # родитель — чёрный bold 11pt
    reqs.append({"repeatCell": {
        "range": {"sheetId": sid,
                  "startRowIndex": parent-1, "endRowIndex": parent,
                  "startColumnIndex": 0, "endColumnIndex": 19},
        "cell": {"userEnteredFormat": {"textFormat": {
            "foregroundColor": BLACK,
            "italic": False, "bold": True, "fontSize": 11}}},
        "fields": "userEnteredFormat.textFormat"}})
    # дети — серый italic 10pt (и текст, и значения)
    for r in children:
        reqs.append({"repeatCell": {
            "range": {"sheetId": sid,
                      "startRowIndex": r-1, "endRowIndex": r,
                      "startColumnIndex": 0, "endColumnIndex": 19},
            "cell": {"userEnteredFormat": {"textFormat": {
                "foregroundColor": GREY,
                "italic": True, "bold": False, "fontSize": 10}}},
            "fields": "userEnteredFormat.textFormat"}})

sh.batch_update({"requests": reqs})
print(f"[OK] Родителей: {len(BLOCKS)}, детей: {sum(len(c) for _,c in BLOCKS)}")
