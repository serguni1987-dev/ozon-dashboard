src = open("fetch_pending_orders.py", encoding="utf-8").read()

# Меняем лимит на 100 для FBO
old = 'limit = 1000'
new = 'limit = 100  # максимум для FBO'
if old in src:
    src = src.replace(old, new)
    print("[OK] limit = 100 (для совместимости с FBO)")
else:
    print("[?] Не нашёл limit")

# Для FBS метод v3 принимает до 1000, но 100 тоже сработает
open("fetch_pending_orders.py", "w", encoding="utf-8").write(src)
print("Готово.")
