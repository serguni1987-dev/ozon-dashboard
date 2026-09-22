src = open("sheets_sync.py", encoding="utf-8").read()

tail = '''

def main():
    print("=" * 80)
    print("ВЫГРУЗКА В GOOGLE SHEETS")
    print("=" * 80)

    client = get_client()
    sh = client.open_by_key(SHEET_ID)
    print(f"\\nОткрыта таблица: {sh.title}")

    con = sqlite3.connect(DB)

    sync_today(sh, con)
    sync_actions(sh, con)
    sync_prices(sh, con)
    sync_frozen(sh, con)
    sync_money(sh, con)
    sync_result(sh, con)

    con.close()

    print("\\n" + "=" * 80)
    print(f"  ГОТОВО. https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit")
    print("=" * 80)


if __name__ == "__main__":
    main()
'''

if "def main()" not in src:
    src += tail
    open("sheets_sync.py", "w", encoding="utf-8").write(src)
    print("[OK] main() и точка входа добавлены")
else:
    print("[i] main() уже есть — проверяю __name__")
    if "__name__" not in src:
        src += '\n\nif __name__ == "__main__":\n    main()\n'
        open("sheets_sync.py", "w", encoding="utf-8").write(src)
        print("[OK] точка входа добавлена")
    else:
        print("[i] всё уже на месте")
