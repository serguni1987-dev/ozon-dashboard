import re
src = open("parse_xlsx.py", encoding="utf-8").read()

# 1. Заменяем find_latest_xlsx на версию с поддержкой имени
old = """def find_latest_xlsx():
    if not os.path.isdir(DOWNLOADS_DIR):
        print(f"[ERROR] Папка {DOWNLOADS_DIR} не найдена")
        sys.exit(1)
    files = glob.glob(os.path.join(DOWNLOADS_DIR, "*.xlsx"))
    if not files:
        print(f"[ERROR] В папке {DOWNLOADS_DIR} нет .xlsx")
        sys.exit(1)
    return max(files, key=os.path.getmtime)"""

new = """def find_latest_xlsx(explicit=None):
    if not os.path.isdir(DOWNLOADS_DIR):
        print(f"[ERROR] Папка {DOWNLOADS_DIR} не найдена")
        sys.exit(1)
    files = glob.glob(os.path.join(DOWNLOADS_DIR, "*.xlsx"))
    if not files:
        print(f"[ERROR] В папке {DOWNLOADS_DIR} нет .xlsx")
        sys.exit(1)
    if explicit:
        # Ищем по имени (basename)
        matches = [f for f in files if os.path.basename(f) == explicit]
        if not matches:
            print(f"[ERROR] Файл {explicit} не найден в {DOWNLOADS_DIR}")
            sys.exit(1)
        return matches[0]
    return max(files, key=os.path.getmtime)


def parse_args():
    args = {}
    for arg in sys.argv[1:]:
        if arg.startswith("--file="):
            args["file"] = arg.split("=", 1)[1]
    return args"""

if old in src:
    src = src.replace(old, new)
    print("[OK] find_latest_xlsx обновлён")
else:
    print("[?] Не нашёл find_latest_xlsx")

# 2. Обновляем main() — передаём имя файла
old_main = """    path = find_latest_xlsx()
    df, p_from, p_to = parse_file(path)"""

new_main = """    args = parse_args()
    path = find_latest_xlsx(explicit=args.get("file"))
    print(f"Файл: {os.path.basename(path)}")
    df, p_from, p_to = parse_file(path)"""

if old_main in src:
    src = src.replace(old_main, new_main)
    print("[OK] main обновлён")
else:
    print("[?] Не нашёл main")

open("parse_xlsx.py", "w", encoding="utf-8").write(src)
print("\nФайл parse_xlsx.py обновлён.")
print("Использование:")
print("  py parse_xlsx.py                       # самый свежий по mtime")
print("  py parse_xlsx.py --file=analytics.xlsx # конкретный файл")
