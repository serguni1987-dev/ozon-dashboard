import re
src = open("sync_monthly.py", encoding="utf-8").read()

# Ищем где определяется month и year
for i, line in enumerate(src.splitlines(), 1):
    if "month" in line.lower() and ("=" in line or "date.today" in line):
        print(f"{i:>4}: {line}")
