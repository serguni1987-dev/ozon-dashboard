src = open("sync_pnl.py", encoding="utf-8").read()

idx = src.find("lines = [")
end = src.find("]", idx + 100)
print(src[idx:end+1])
