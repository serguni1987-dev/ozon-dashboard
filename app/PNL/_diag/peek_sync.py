import re
src = open("sync_monthly.py", encoding="utf-8").read()

# Ищем блок, где обрабатывается delivery_commission и return_commission
idx = src.find("delivery_commission")
if idx > 0:
    print("=== Фрагмент с delivery_commission ===")
    print(src[idx-300:idx+3000])
