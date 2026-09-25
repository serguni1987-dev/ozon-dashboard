"""patch_dropoff_agent_v2.py — добавляет 17: "Логистика" в CATEGORY_MAP."""

src = open("PNL/sync_pnl.py", encoding="utf-8").read()

# Ищем точную строку из CATEGORY_MAP
OLD = '12: "Услуги FBO", 16: "Логистика", 38: "Обработка, сборка",'
NEW = '12: "Услуги FBO", 16: "Логистика", 17: "Логистика", 38: "Обработка, сборка",'

if OLD in src:
    src = src.replace(OLD, NEW, 1)
    print("[OK] Добавлен 17 в CATEGORY_MAP")
elif '17: "Логистика", 38:' in src:
    print("[i] Уже есть")
else:
    print("[?] Не нашёл строку с 16: Логистика")

open("PNL/sync_pnl.py", "w", encoding="utf-8").write(src)
print("[OK] сохранён")