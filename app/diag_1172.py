lines = open("sheets_sync.py", encoding="utf-8-sig").read().splitlines()
print(f"Всего строк: {len(lines)}")
print("\nСтроки 1165-1185:")
for i in range(1164, min(1186, len(lines))):
    print(f"{i+1}: {lines[i]!r}")
