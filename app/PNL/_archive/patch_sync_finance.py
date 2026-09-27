src = open("sync_finance.py", encoding="utf-8").read()

old = '''START_DEFAULT = "2026-09-01"
END = datetime.now().strftime("%Y-%m-%d")'''

new = '''START_DEFAULT = "2026-09-01"
END = datetime.now().strftime("%Y-%m-%d")

# Переопределяется через --from и --to
def parse_args():
    args = {"date_from": None, "date_to": None}
    for arg in sys.argv[1:]:
        if arg.startswith("--from="):
            args["date_from"] = arg.split("=", 1)[1]
        elif arg.startswith("--to="):
            args["date_to"] = arg.split("=", 1)[1]
    return args'''

if old in src:
    src = src.replace(old, new)
    print("[OK] Добавлены параметры --from / --to")
else:
    print("[?] Не нашёл START_DEFAULT")

# Добавляем import sys
if "import sys" not in src:
    src = src.replace("import os\n", "import os\nimport sys\n", 1)
    print("[OK] import sys добавлен")

# Меняем main — используем параметры
old2 = '''def main():
    print("=" * 80)
    print("СИНХРОНИЗАЦИЯ ФИНАНСОВ ИЗ OZON API")
    print("=" * 80)

    con = sqlite3.connect(DB)
    cur = con.cursor()

    start = get_start_date(cur)
    print(f"\\n[1] Период синхронизации: {start} — {END}")

    if start > END:
        print("  Данные уже актуальны.")
        con.close()
        return'''

new2 = '''def main():
    args = parse_args()
    print("=" * 80)
    print("СИНХРОНИЗАЦИЯ ФИНАНСОВ ИЗ OZON API")
    print("=" * 80)

    con = sqlite3.connect(DB)
    cur = con.cursor()

    # Период
    if args["date_from"]:
        start = args["date_from"]
    else:
        start = get_start_date(cur)
    end = args["date_to"] or END

    print(f"\\n[1] Период синхронизации: {start} — {end}")

    if start > end:
        print("  Данные уже актуальны.")
        con.close()
        return'''

if old2 in src:
    src = src.replace(old2, new2)
    print("[OK] main использует --from / --to")
else:
    print("[?] Не нашёл main")

# Меняем END в цикле на end
src = src.replace(
    'end = datetime.strptime(END, "%Y-%m-%d")',
    'end_dt = datetime.strptime(end, "%Y-%m-%d")'
)
src = src.replace(
    'while d <= end:',
    'while d <= end_dt:'
)

open("sync_finance.py", "w", encoding="utf-8").write(src)
print("\nГотово. Запускай: py sync_finance.py --from=2026-08-01 --to=2026-08-31")
