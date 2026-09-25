import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "PNL"))
import gspread
from google.oauth2.service_account import Credentials
import sync_pnl

creds = Credentials.from_service_account_file(
    "credentials.json",
    scopes=["https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"]
)
ws = gspread.authorize(creds).open_by_key(sync_pnl.SHEET_ID).worksheet("P&L")

print("H37 (значение):", repr(ws.acell("H37").value))
print("B37 (формула):", repr(ws.acell("B37", value_render_option="FORMULA").value))
print("B37 (значение):", repr(ws.acell("B37").value))
print("H36 (формула):", repr(ws.acell("H36", value_render_option="FORMULA").value))
print("H36 (значение):", repr(ws.acell("H36").value))
print("P37 (значение):", repr(ws.acell("P37").value))
print("B36 (формула):", repr(ws.acell("B36", value_render_option="FORMULA").value))
print("B36 (значение):", repr(ws.acell("B36").value))