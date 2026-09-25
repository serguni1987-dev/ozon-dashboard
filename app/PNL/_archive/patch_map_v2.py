src = open("PNL/sync_pnl.py", encoding="utf-8").read()

# 12 CrossDock → FBO, 16 Drop-Off → Логистика
old = '12: "Обработка, сборка", 16: "Обработка, сборка", 38: "Обработка, сборка",'
new = '12: "Услуги FBO", 16: "Логистика", 38: "Обработка, сборка",'
if old in src:
    src = src.replace(old, new, 1)
    print("[OK] 12 → FBO, 16 → Логистика")
else:
    print("[?] Не нашёл строку. Проверь:")
    for line in src.splitlines():
        if "CrossDock" in line or "12:" in line or "16:" in line:
            print("  >", line)

open("PNL/sync_pnl.py", "w", encoding="utf-8").write(src)
print("[OK] сохранён")