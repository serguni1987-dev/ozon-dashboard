"""patch_run_sync.py — добавляет sync_monthly.py в run.py.
Он сам проверит, загружен ли прошлый месяц, и либо загрузит, либо пропустит.
"""

src = open("run.py", encoding="utf-8").read()

# Ищем блок "# 3. Финансы из API"
OLD = '''    # 3. Финансы из API
    print("\\n[3] Синхронизация финансов из Ozon API...")
    run([PY, "sync_finance.py"], stop_on_error=False)
'''

NEW = '''    # 2.5. Отчёт о реализации за прошлый месяц (с защитой от перезаписи)
    print("\\n[2.5] Отчёт о реализации за прошлый месяц...")
    run([PY, "sync_monthly.py"], stop_on_error=False)

    # 3. Финансы из API
    print("\\n[3] Синхронизация финансов из Ozon API...")
    run([PY, "sync_finance.py"], stop_on_error=False)
'''

if OLD in src:
    src = src.replace(OLD, NEW, 1)
    print("[OK] Добавлен вызов sync_monthly.py")
elif "sync_monthly.py" in src:
    print("[i] Уже добавлено")
else:
    print("[?] Не нашёл блок '# 3. Финансы из API'")
    print("    Найди вручную строку с sync_finance.py")

open("run.py", "w", encoding="utf-8").write(src)
print("[OK] run.py сохранён")