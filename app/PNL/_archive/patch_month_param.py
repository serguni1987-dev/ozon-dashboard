src = open("sync_monthly.py", encoding="utf-8").read()

old = '''    today = date.today()
    prev = today - relativedelta(months=1)
    month = prev.month
    year = prev.year
    month_str = f"{year}-{month:02d}"'''

new = '''    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", default=None, help="YYYY-MM")
    args, _ = parser.parse_known_args()

    if args.month:
        parts = args.month.split("-")
        year = int(parts[0])
        month = int(parts[1])
        month_str = args.month
    else:
        today = date.today()
        prev = today - relativedelta(months=1)
        month = prev.month
        year = prev.year
        month_str = f"{year}-{month:02d}"'''

if old in src:
    src = src.replace(old, new)
    open("sync_monthly.py", "w", encoding="utf-8").write(src)
    print("[OK] Параметр --month добавлен")
else:
    print("[?] Не нашёл блок")
