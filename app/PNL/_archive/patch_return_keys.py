import re
src = open("sync_pnl.py", encoding="utf-8").read()

# 1. Добавить 5 ключей в return
old = '"cogs": cogs, "fulfil_logistics": cats.get("Логистика", 0),'
new = ('"cogs": cogs,\n'
       '        "fulfil_logistics":  cats.get("Логистика", 0),\n'
       '        "fulfil_reverse":    cats.get("Обратная логистика", 0),\n'
       '        "fulfil_lastmile":   cats.get("Последняя миля", 0),\n'
       '        "fulfil_processing": cats.get("Обработка, сборка", 0),\n'
       '        "fulfil_total":     (cats.get("Логистика", 0)\n'
       '                              + cats.get("Обратная логистика", 0)\n'
       '                              + cats.get("Последняя миля", 0)\n'
       '                              + cats.get("Обработка, сборка", 0)),\n'
       '        "reviews":           cats.get("Отзывы", 0),')
if old in src:
    src = src.replace(old, new, 1)
    print("[OK] 5 ключей добавлены в return")
else:
    print("[?] Не нашёл 'cogs ... fulfil_logistics'")

open("sync_pnl.py", "w", encoding="utf-8").write(src)
print("[OK] sync_pnl.py сохранён")