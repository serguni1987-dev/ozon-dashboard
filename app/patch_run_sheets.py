import re
src = open("run.py", encoding="utf-8").read()

# Добавляем шаг sheets_sync между sync_archived и daily_dashboard
old = '''    # 5. Пульт
    print("\\n[5] Открываю пульт...")
    run([PY, "daily_dashboard.py"])'''

new = '''    # 5. Выгрузка в Google Sheets
    print("\\n[5] Выгружаю в Google Sheets...")
    run([PY, "sheets_sync.py"], stop_on_error=False)

    # 6. Пульт (локально)
    print("\\n[6] Открываю пульт...")
    run([PY, "daily_dashboard.py"])'''

if old in src:
    src = src.replace(old, new)
    open("run.py", "w", encoding="utf-8").write(src)
    print("[OK] run.py обновлён: добавлен шаг sheets_sync")
else:
    print("[?] Не нашёл место для патча. Открой run.py и добавь вручную перед daily_dashboard.py:")
    print("    run([PY, 'sheets_sync.py'], stop_on_error=False)")
