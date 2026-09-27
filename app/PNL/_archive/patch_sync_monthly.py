"""patch_sync_monthly.py — защита от перезаписи закрытого месяца.
1. Добавляет --force
2. Перед DELETE проверяет: месяц уже есть в monthly_reports?
   Если да и не --force → печатает "уже загружено" и выходит.
"""

src = open("sync_monthly.py", encoding="utf-8").read()

# ── 1. Добавить --force ──
OLD_ARGS = '''    parser.add_argument("--month", default=None, help="YYYY-MM")
    args, _ = parser.parse_known_args()'''

NEW_ARGS = '''    parser.add_argument("--month", default=None, help="YYYY-MM")
    parser.add_argument("--force", action="store_true",
                        help="Перезаписать уже загруженный месяц")
    args, _ = parser.parse_known_args()'''

if OLD_ARGS in src:
    src = src.replace(OLD_ARGS, NEW_ARGS, 1)
    print("[OK] Добавлен --force")
else:
    print("[?] Не нашёл argparse-блок")

# ── 2. Проверка перед DELETE ──
OLD_DELETE = '''    con = sqlite3.connect(DB)
    init_tables(con)
    con.execute("DELETE FROM monthly_realization_rows WHERE month = ?", (month_str,))'''

NEW_DELETE = '''    con = sqlite3.connect(DB)
    init_tables(con)

    # ── Проверка "уже загружено" ──
    existing = con.execute(
        "SELECT report_number, fetched_at FROM monthly_reports WHERE month = ?",
        (month_str,)
    ).fetchone()

    if existing and not args.force:
        print()
        print(f"[i] Месяц {month_str} уже загружен:")
        print(f"    Отчёт №{existing[0]}, загружен {existing[1]}")
        print(f"    Для перезаписи используй --force")
        print(f"    Или удали запись из monthly_reports вручную")
        con.close()
        return

    if existing and args.force:
        print()
        print(f"[!] --force: перезаписываю {month_str} (старый отчёт №{existing[0]})")

    con.execute("DELETE FROM monthly_realization_rows WHERE month = ?", (month_str,))'''

if OLD_DELETE in src:
    src = src.replace(OLD_DELETE, NEW_DELETE, 1)
    print("[OK] Добавлена проверка перед DELETE")
else:
    print("[?] Не нашёл блок DELETE")

open("sync_monthly.py", "w", encoding="utf-8").write(src)
print("[OK] sync_monthly.py сохранён")