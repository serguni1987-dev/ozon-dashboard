src = open("sheets_sync.py", encoding="utf-8").read()

# Ищем все print(\n[ → print("\n[
fixed = 0
while 'print(\\n[' in src:
    src = src.replace('print(\\n[', 'print("\\n[', 1)
    fixed += 1

# То же с print(\n  — без [
while 'print(\\n ' in src:
    src = src.replace('print(\\n ', 'print("\\n ', 1)
    fixed += 1

# На всякий случай — общий шаблон: print(\\nX → print("\\nX
import re
src, n2 = re.subn(r'print\(\\n([^"])', r'print("\\n\1', src)
fixed += n2

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print(f"[OK] Исправлено: {fixed}")
