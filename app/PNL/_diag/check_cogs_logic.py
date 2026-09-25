src = open("PNL/sync_pnl.py", encoding="utf-8").read().splitlines()
for i, line in enumerate(src, 1):
    if "real_skus" in line or "cogs" in line.lower() or "Fallback" in line:
        print(f"{i:>4}  {line}")