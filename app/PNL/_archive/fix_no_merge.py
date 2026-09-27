src = open("sync_fact.py", encoding="utf-8").read()

# Убираем блок с unmerge и merge
old = '''    # Снимаем старые merge (только на конкретных диапазонах, чтобы не ругался)
    for rng in ["A1:C1", "A2:C2"]:
        reqs.append({"unmergeCells": {"range": grid(rng)}})

    # Заголовок
    reqs.append({"mergeCells": {"range": grid("A1:C1"), "mergeType": "MERGE_ALL"}})
    fmt("A1:C1", bg=DARK, fg=WHITE, bold=True, size=14, align="CENTER")

    # Подзаголовок
    reqs.append({"mergeCells": {"range": grid("A2:C2"), "mergeType": "MERGE_ALL"}})
    fmt("A2:C2", bg=GREY, bold=True, size=11, align="CENTER")'''

new = '''    # Без merge — просто форматирование ячеек
    fmt("A1:C1", bg=DARK, fg=WHITE, bold=True, size=14, align="CENTER")
    fmt("A2:C2", bg=GREY, bold=True, size=11, align="CENTER")'''

if old in src:
    src = src.replace(old, new)
    open("sync_fact.py", "w", encoding="utf-8").write(src)
    print("[OK] Убраны unmerge и merge")
else:
    print("[?] Не нашёл блок merge")
