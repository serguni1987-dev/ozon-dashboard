src = open("PNL/sync_pnl.py", encoding="utf-8").read().splitlines()
for k in range(99, 161):
    if k < len(src):
        print(f"{k+1:>4}  {src[k]}")