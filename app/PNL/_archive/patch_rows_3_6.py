src = open("pnl_format.py", encoding="utf-8").read()
anchor = "    for r in (47,48):"
if anchor in src and "for r in (3,4,5,6):" not in src:
    add = ('    for r in (3,4,5,6):\n'
           '        reqs.append({"repeatCell":{"range":grid(sid,r-1,r),\n'
           '            "cell":{"userEnteredFormat":cell(bg=WHITE,fg=BLACK,italic=False,size=11)},\n'
           '            "fields":"userEnteredFormat"}})\n')
    src = src.replace(anchor, add + anchor, 1)
    open("pnl_format.py", "w", encoding="utf-8").write(src)
    print("[OK] строки 3-6 добавлены как обычные")
elif "for r in (3,4,5,6):" in src:
    print("[i] уже есть")
else:
    print("[?] Не нашёл anchor")