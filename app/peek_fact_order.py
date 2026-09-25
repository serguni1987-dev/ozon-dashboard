src = open("sync_fact.py", encoding="utf-8").read()

# Находим блок с прямыми расходами и себестоимостью
old = '''    # ПРЯМЫЕ РАСХОДЫ
    rows.append(["Прямые (переменные) расходы (всего)", round(-direct, 2), pct(-direct)])
    rows.append(["  Озон комиссия (за вычетом возвратов)", round(-d["commission"], 2), pct(-d["commission"])])'''

new = '''    # ПРЯМЫЕ РАСХОДЫ
    rows.append(["Прямые (переменные) расходы (всего)", round(-direct, 2), pct(-direct)])
    rows.append(["  Озон комиссия (за вычетом возвратов)", round(-d["commission"], 2), pct(-d["commission"])])'''

# Проверяем, что структура в коде
if old in src:
    print("[i] Блок прямых расходов на месте")
else:
    print("[?] Не нашёл блок прямых расходов")

# Ищем, где сейчас строка себестоимости
idx = src.find('rows.append(["  Себестоимость с учётом возвратов"')
if idx > 0:
    print(f"[i] Строка себестоимости найдена в позиции {idx}")
    # Показываем контекст
    print(src[idx-300:idx+300])
else:
    print("[?] Не нашёл строку себестоимости")
