import os, gspread
from google.oauth2.service_account import Credentials
import sync_pnl

CRED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file(CRED, scopes=SCOPES)
ws = gspread.authorize(creds).open_by_key(sync_pnl.SHEET_ID).worksheet("P&L")

# Значения (то, что видим)
vals = ws.get_all_values()
print("── Значения (как видно) ──────────────")
for addr, r, c in [("H33",33,8), ("J33",33,10), ("J34",34,10),
                    ("J39",39,10), ("J43",43,10), ("J44",44,10)]:
    row = vals[r-1] if r-1 < len(vals) else []
    v = row[c-1] if c-1 < len(row) else ""
    print(f"  {addr} = {v!r}")

# Формулы (как хранит Google)
print("\n── Формулы (value_render=FORMULA) ────")
for addr in ("H33","J33","J39","J43","J44"):
    try:
        f = ws.acell(addr, value_render_option="FORMULA").value
        print(f"  {addr} = {f!r}")
    except Exception as e:
        print(f"  {addr}: ошибка {e}")
