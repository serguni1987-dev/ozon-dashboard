src = open("diag_cogs.py", encoding="utf-8").read()

# Заменяем r.items() на dict(r).items()
src = src.replace("for k, v in r.items():", "for k, v in dict(r).items():")

open("diag_cogs.py", "w", encoding="utf-8").write(src)
print("[OK] Исправлено")
