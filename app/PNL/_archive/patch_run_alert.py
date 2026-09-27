"""patch_run_alert.py — вставляет mark_brands и check_costs_alert в run.py.
Было:  [6] архив → [7] decisions → [8] sheets → ...
Стало: [6] архив → [7] mark_brands → [8] alert → [9] decisions → [10] sheets → ...
"""

src = open("run.py", encoding="utf-8").read()

OLD = '''    # 7. Решения из Google Sheets
    print("\\n[7] Синхронизация решений из Google Sheets...")
    run([PY, "sync_decisions.py"], stop_on_error=False)

    # 8. Google Sheets
    print("\\n[8] Выгружаю в Google Sheets...")
    run([PY, "sheets_sync.py"], stop_on_error=False)

    # 9. Локальный пульт
    print("\\n[9] Открываю пульт...")
    run([PY, "daily_dashboard.py"])

    # 10. Дневник решений
    if not skip_effects:
        print("\\n[10] Дневник решений...")
        run([PY, "decision_effects.py"], stop_on_error=False)
'''

NEW = '''    # 7. Помечаем свои/чужие (SKU из отчёта реализации → is_own=1)
    print("\\n[7] Помечаю свои SKU...")
    run([PY, "mark_brands.py"], stop_on_error=False)

    # 8. Контроль себестоимости (алерт, не блокирующий)
    print("\\n[8] Проверка себестоимости...")
    run([PY, "check_costs_alert.py"], stop_on_error=False)

    # 9. Решения из Google Sheets
    print("\\n[9] Синхронизация решений из Google Sheets...")
    run([PY, "sync_decisions.py"], stop_on_error=False)

    # 10. Google Sheets
    print("\\n[10] Выгружаю в Google Sheets...")
    run([PY, "sheets_sync.py"], stop_on_error=False)

    # 11. Локальный пульт
    print("\\n[11] Открываю пульт...")
    run([PY, "daily_dashboard.py"])

    # 12. Дневник решений
    if not skip_effects:
        print("\\n[12] Дневник решений...")
        run([PY, "decision_effects.py"], stop_on_error=False)
'''

if OLD in src:
    src = src.replace(OLD, NEW, 1)
    print("[OK] Вставлены шаги 7 (mark_brands) и 8 (check_costs_alert)")
else:
    print("[?] Не нашёл блок. Возможно, отличается отступ или кавычки.")
    print("    Найди вручную строку '# 7. Решения из Google Sheets'")

# Также обновим нумерацию [11] backup_db → [13]
if "# 11. Резервная копия базы" in src:
    src = src.replace("# 11. Резервная копия базы", "# 13. Резервная копия базы", 1)
    src = src.replace('print("\\n[11] Резервная копия базы...")', 'print("\\n[13] Резервная копия базы...")', 1)
    print("[OK] backup_db перенумерован в [13]")

open("run.py", "w", encoding="utf-8").write(src)
print("[OK] run.py сохранён")