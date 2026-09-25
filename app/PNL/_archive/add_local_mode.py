src = open("sync_pnl.py", encoding="utf-8").read()

# В main добавляем проверку --local
old = '''def main():
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2026

    print("=" * 80)
    print(f"ВЫГРУЗКА P&L ЗА {year}")
    print("=" * 80)

    rows = build_table(year)
    print(f"\\nСтрок: {len(rows)}")

    scopes = ["https://www.googleapis.com/auth/spreadsheets",
              "https://www.googleapis.com/auth/drive"]'''

new = '''def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    year = int(args[0]) if args else 2026
    local = "--local" in sys.argv

    print("=" * 80)
    print(f"ВЫГРУЗКА P&L ЗА {year}  {'(локально)' if local else ''}")
    print("=" * 80)

    rows = build_table(year)
    print(f"\\nСтрок: {len(rows)}")

    if local:
        # Сохраняем локально в CSV
        import csv
        out = os.path.join(APP_DIR, f"pnl_{year}.csv")
        with open(out, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerows(rows)
        print(f"\\n[OK] Сохранено: {out}")
        # Печатаем ключевые строки
        print()
        for row in rows:
            a = row[0] if row else ""
            b = row[1] if len(row) > 1 else ""
            print(f"  {a:<50} {b}")
        return

    scopes = ["https://www.googleapis.com/auth/spreadsheets",
              "https://www.googleapis.com/auth/drive"]'''

if old in src:
    src = src.replace(old, new)
    open("sync_pnl.py", "w", encoding="utf-8").write(src)
    print("[OK] Добавлен режим --local")
else:
    print("[?] Не нашёл main()")
