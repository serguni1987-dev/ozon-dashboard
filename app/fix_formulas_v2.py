# fix_formulas_v2.py — исправляет знак в J43 и убирает IF из J44
import os, gspread
from google.oauth2.service_account import Credentials
import sync_pnl

CRED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file(CRED, scopes=SCOPES)
ws = gspread.authorize(creds).open_by_key(sync_pnl.SHEET_ID).worksheet("P&L")

def col_letter(n):
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s

cols = ["B"] + [col_letter(i) for i in range(3, 15)] + ["O","P","Q","R"]

updates = []
for col in cols:
    # 33: SUM(34:37)
    updates.append({"range": f"{col}33",
                    "values": [[f"=SUM({col}34:{col}37)"]]})
    # 39: EBITDA = 31 - 33
    updates.append({"range": f"{col}39",
                    "values": [[f"={col}31-{col}33"]]})
    # 43: Чистая = 39 + 41 (J41 хранится уже со знаком минус)
    updates.append({"range": f"{col}43",
                    "values": [[f"={col}39+{col}41"]]})
    # 44: ROI без IF, без запятых — иначе ломается русская локаль
    updates.append({"range": f"{col}44",
                    "values": [[f"=-{col}43/{col}29*100"]]})

ws.batch_update(updates, value_input_option="USER_ENTERED")
print(f"[OK] Записано {len(updates)} формул")

print("\n── Контроль ──────────────────────────")
for addr in ("J33", "J39", "J43", "J44"):
    f = ws.acell(addr, value_render_option="FORMULA").value
    v = ws.acell(addr).value
    print(f"  {addr}: формула={f!r}  значение={v!r}")
