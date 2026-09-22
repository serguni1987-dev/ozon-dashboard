src = open("sheets_sync.py", encoding="utf-8").read()
lines = src.splitlines()
print("Всего строк:", len(lines))
print("\nСтроки 1612-1625:")
for i in range(1611, min(1626, len(lines))):
    print(f"{i+1}: {lines[i]!r}")
