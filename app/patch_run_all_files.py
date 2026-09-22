src = open("run.py", encoding="utf-8").read()

old = """    # 1-2. Новые .xlsx
    new_files = list_new_files()
    if new_files:
        print(f"\\n[1] Найдено новых .xlsx: {len(new_files)}")
        for f in new_files:
            print(f"    • {os.path.basename(f)}")
        print("\\n[2] Запускаю parse_xlsx.py...")
        run([PY, "parse_xlsx.py"])
    else:
        print("\\n[1] Новых .xlsx нет. Использую текущие данные.")"""

new = """    # 1-2. Новые .xlsx — обрабатываем ВСЕ
    new_files = list_new_files()
    if new_files:
        print(f"\\n[1] Найдено новых .xlsx: {len(new_files)}")
        for f in new_files:
            print(f"    • {os.path.basename(f)}")
        print(f"\\n[2] Обрабатываю каждый по очереди...")
        for f in new_files:
            fname = os.path.basename(f)
            print(f"\\n    --- {fname} ---")
            run([PY, "parse_xlsx.py", f"--file={fname}"], stop_on_error=False)
    else:
        print("\\n[1] Новых .xlsx нет. Использую текущие данные.")"""

if old in src:
    src = src.replace(old, new)
    open("run.py", "w", encoding="utf-8").write(src)
    print("[OK] run.py обновлён: обрабатывает все новые .xlsx")
else:
    print("[?] Не нашёл блок. Патчим вручную.")
