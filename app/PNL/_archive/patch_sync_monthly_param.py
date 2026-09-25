"""
patch_sync_monthly_param.py - добавляет параметр --month.
"""
src = open("sync_monthly.py", encoding="utf-8").read()

# Ищем блок определения месяца
old = '''    # Определяем предыдущий месяц
    today = date.today()
    prev = today - relativedelta(months=1)
    month = prev.month
    year = prev.year
    month_str = f"{year}-{month:02d}"'''

new = '''    # Месяц: из --month=YYYY-MM или предыдущий месяц
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", default=None, help="YYYY-MM")
    args, _ = parser.parse_known_args()

    if args.month:
        y, m = args.month.split("-")
        year = int(y)
        month = int(m)
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
    print("[?] Не нашёл блок определения месяца")
    # Покажем что есть
    idx = src.find("prev = today")
    if idx > 0:
        print(src[idx-200:idx+300])
