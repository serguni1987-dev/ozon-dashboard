src = open("sheets_sync.py", encoding="utf-8").read()

# В build_result margin должен храниться как доля (0.065), не как проценты
old = "    margin = profit / rev * 100 if rev else 0"
new = "    margin = profit / rev if rev else 0"

n = src.count(old)
src = src.replace(old, new)
open("sheets_sync.py", "w", encoding="utf-8").write(src)
print(f"[OK] Заменено вхождений margin: {n}")
