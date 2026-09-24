import os, gspread
from google.oauth2.service_account import Credentials
import sync_pnl
CRED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file(CRED, scopes=SCOPES)
ws = gspread.authorize(creds).open_by_key(sync_pnl.SHEET_ID).worksheet("P&L")
sid = ws.id
BLACK = {"red":0.0,"green":0.0,"blue":0.0}
reqs = []
for r in (3,4,5,6):
    reqs.append({"repeatCell": {
        "range": {"sheetId":sid,"startRowIndex":r-1,"endRowIndex":r,
                  "startColumnIndex":0,"endColumnIndex":19},
        "cell": {"userEnteredFormat":{"textFormat":{
            "foregroundColor":BLACK,"italic":False,"bold":False,"fontSize":11}}},
        "fields":"userEnteredFormat.textFormat"}})
ws.spreadsheet.batch_update({"requests": reqs})
print("[OK] строки 3-6 обычные чёрные")
