src = open("daily_dashboard.py", encoding="utf-8").read()

# Ищем вхождения "MIN(date)" и "весь период"
print("=== MIN(date) ===")
for i, line in enumerate(src.splitlines(), 1):
    if "MIN(date)" in line or "весь период" in line:
        print(f"  {i}: {line.strip()}")

print("\n=== build_result начало ===")
idx = src.find("def block_result")
if idx < 0:
    idx = src.find("def build_result")
if idx > 0:
    print(src[idx:idx+700])
