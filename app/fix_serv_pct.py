src = open("sheets_sync.py", encoding="utf-8").read()

# serv_pct_30 берёт profit (s30[4]) вместо serv (s30[3])
old = "    serv_pct_30 = s30[4] / s30[0] if s30[0] else 0"
new = "    serv_pct_30 = s30[3] / s30[0] if s30[0] else 0"

if old in src:
    src = src.replace(old, new)
    open("sheets_sync.py", "w", encoding="utf-8").write(src)
    print("[OK] serv_pct_30: s30[4] → s30[3] (услуги, не прибыль)")
else:
    print("[?] Не нашёл. Проверь: grep 'serv_pct_30' в sheets_sync.py")
