import re

src = open("sheets_sync.py", encoding="utf-8").read()
new_funcs = open("new_money_functions.py", encoding="utf-8").read()

# Удаляем старые функции
src = re.sub(r"def build_money\(con\):.*?(?=\ndef )", "", src, flags=re.DOTALL)
src = re.sub(r"def format_money\(ws.*?\):.*?(?=\ndef )", "", src, flags=re.DOTALL)
src = re.sub(r"def sync_money\(sh, con\):.*?(?=\ndef )", "", src, flags=re.DOTALL)

# Вставляем новые перед def build_result
if "def build_result" in src:
    src = src.replace("def build_result(con):", new_funcs + "\n\ndef build_result(con):", 1)
    print("[OK] Новые функции вставлены")
else:
    print("[FAIL] Не нашёл build_result")

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("Готово.")
