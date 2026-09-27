src = open("run.py", encoding="utf-8").read()

old = """    # 8. Отчёт по решениям (после пульта, т.к. он не очищает экран)
    if not skip_effects:
        print("\\n[8] Дневник решений...")
        run([PY, "decision_effects.py"], stop_on_error=False)"""

new = """    # 8. Отчёт по решениям (после пульта, т.к. он не очищает экран)
    if not skip_effects:
        print("\\n[8] Дневник решений...")
        run([PY, "decision_effects.py"], stop_on_error=False)

    # 9. Резервная копия базы
    print("\\n[9] Резервная копия базы...")
    run([PY, "backup_db.py"], stop_on_error=False)"""

if old in src:
    src = src.replace(old, new)
    open("run.py", "w", encoding="utf-8").write(src)
    print("[OK] backup встроен в run.py")
else:
    print("[?] Не нашёл место. Вставь вручную в конец main():")
    print("    run([PY, 'backup_db.py'], stop_on_error=False)")
