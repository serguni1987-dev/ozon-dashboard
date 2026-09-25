"""patch_dropoff_agent.py — добавляет type_id=17 (Drop-Off Agent) в Логистику."""

src = open("PNL/sync_pnl.py", encoding="utf-8").read()

# Ищем строку с 16: "Логистика" и добавляем 17 рядом
OLD = '16: "Логистика"'
NEW = '16: "Логистика",\n    17: "Логистика"'

if OLD in src and "17:" not in src:
    src = src.replace(OLD, NEW, 1)
    print("[OK] Добавлен type_id=17 → Логистика")
elif "17:" in src:
    print("[i] Уже добавлен")
else:
    print("[?] Не нашёл '16: \"Логистика\"' — проверь вручную")

open("PNL/sync_pnl.py", "w", encoding="utf-8").write(src)
print("[OK] PNL/sync_pnl.py сохранён")