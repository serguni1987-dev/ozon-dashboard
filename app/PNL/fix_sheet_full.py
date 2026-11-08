# fix_sheet_full.py — живые формулы в B, C:N, O:R (50 строк).
import os, gspread
from google.oauth2.service_account import Credentials
import sys as _sys
import os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import sync_pnl

CRED=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),"credentials.json")
SCOPES=["https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"]
creds=Credentials.from_service_account_file(CRED,scopes=SCOPES)
ws=gspread.authorize(creds).open_by_key(sync_pnl.SHEET_ID).worksheet("P&L")

def cl(n):
    s=""
    while n>0:
        n,r=divmod(n-1,26); s=chr(65+r)+s
    return s

MONTHS=[cl(i) for i in range(4,16)]  # D..O
QUARTERS={"P":("D","F"),"Q":("G","I"),"R":("J","L"),"S":("M","O")}

SUM_ROWS=[3,4,5,6, 8,9,10,11,12, 14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,
          32, 34, 37,38,39,40, 44]   # 49 и 50 — формулы ниже (нераспределённая / накопленная)

u=[]
for r in SUM_ROWS:
    u.append({"range":f"B{r}","values":[[f"=SUM(D{r}:O{r})"]]})
u.append({"range":"B36","values":[["=SUM(B37:B40)"]]})
u.append({"range":"B42","values":[["=B34+B36"]]})
u.append({"range":"B46","values":[["=B42+B44"]]})
u.append({"range":"B47","values":[["=IF(B32=0;0;-B46/B32*100)"]]})
u.append({"range":"B49","values":[["=SUM(D49:O49)"]]})
u.append({"range":"B50","values":[["=B49"]]})          # накопленная за год = нераспределённая за год
for r in (36,42,46,49,50):                              # колонка C — % от годовых доходов
    u.append({"range":f"C{r}","values":[[f"=IF($B$5=0;0;B{r}/$B$5*100)"]]})
u.append({"range":"C47","values":[["=B47"]]})

for col in MONTHS:
    u.append({"range":f"{col}36","values":[[f"=SUM({col}37:{col}40)"]]})
    u.append({"range":f"{col}42","values":[[f"={col}34+{col}36"]]})
    u.append({"range":f"{col}46","values":[[f"={col}42+{col}44"]]})
    u.append({"range":f"{col}47","values":[[f"=IF({col}32=0;0;-{col}46/{col}32*100)"]]})
    u.append({"range":f"{col}49","values":[[f"={col}46+{col}48"]]})      # чистая + дивиденды
    u.append({"range":f"{col}50","values":[[f"=SUM($D$49:{col}49)"]]})  # нарастающим итогом

for qcol,(m1,m2) in QUARTERS.items():
    for r in SUM_ROWS:
        u.append({"range":f"{qcol}{r}","values":[[f"=SUM({m1}{r}:{m2}{r})"]]})
    u.append({"range":f"{qcol}36","values":[[f"=SUM({qcol}37:{qcol}40)"]]})
    u.append({"range":f"{qcol}42","values":[[f"={qcol}34+{qcol}36"]]})
    u.append({"range":f"{qcol}46","values":[[f"={qcol}42+{qcol}44"]]})
    u.append({"range":f"{qcol}47","values":[[f"=IF({qcol}32=0;0;-{qcol}46/{qcol}32*100)"]]})
    u.append({"range":f"{qcol}49","values":[[f"=SUM({m1}49:{m2}49)"]]})
    u.append({"range":f"{qcol}50","values":[[f"=SUM($D$49:{m2}49)"]]})

ws.batch_update(u,value_input_option="USER_ENTERED")
print(f"[OK] Записано {len(u)} формул")

print("\n── Контроль ──────────────────────────")
for addr in ("B8","B14","B16","B21","B34","B36","B42","B44","B46","B47","J22","J26","O34","R46"):
    f=ws.acell(addr,value_render_option="FORMULA").value
    v=ws.acell(addr).value
    print(f"  {addr}: формула={f!r}  значение={v!r}")