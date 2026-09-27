import gspread, re
from google.oauth2.service_account import Credentials

src = open("sheets_sync.py", encoding="utf-8").read()
SHEET_ID = re.search(r'SHEET_ID\s*=\s*"([^"]+)"', src).group(1)

scopes = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
client = gspread.authorize(creds)
sh = client.open_by_key(SHEET_ID)
ws = sh.worksheet("ФАКТ")

vals = ws.get_all_values()
print(f"Строк в листе: {len(vals)}")
print()
for i, row in enumerate(vals, 1):
    a = (row[0] if len(row) > 0 else "")[:55]
    b = row[1] if len(row) > 1 else ""
    print(f"{i:>3}  {a:<57} {b}")
