import os, gspread
from google.oauth2.service_account import Credentials
import sync_pnl

CRED = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file(CRED, scopes=SCOPES)
ws = gspread.authorize(creds).open_by_key(sync_pnl.SHEET_ID).worksheet("P&L")

print("=== 1. Прямая проверка H37 ===")
print(f"  H37 = {ws.acell('H37').value!r}")
print(f"  H37 (unformatted) = {ws.acell('H37', value_render_option='UNFORMATTED_VALUE').value!r}")

print()
print("=== 2. Что вернёт row_values(37) ===")
row = ws.row_values(37)
print(f"  Длина: {len(row)}")
for i, v in enumerate(row):
    col = chr(65 + i) if i < 26 else f"col{i+1}"
    print(f"    idx={i}  {col}37 = {v!r}")

print()
print("=== 3. read_operational результат ===")
saved = sync_pnl.read_operational(ws)
print(f"  saved = {saved}")
print(f"  Ключей: {len(saved)}")

print()
print("=== 4. Код read_operational ===")
import inspect
print(inspect.getsource(sync_pnl.read_operational))