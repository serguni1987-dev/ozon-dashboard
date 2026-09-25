src = open("sync_pnl.py", encoding="utf-8").read()

# Возвращаем -1 для месяцев
old1 = '''        # Значения по месяцам (mcol даёт 1-based колонку)
        for m_str, data in by_month.items():
            m_num = int(m_str.split("-")[1])
            val = data.get(key, 0)
            if key in NEGATIVE:
                val = -abs(val)
            row[mcol(m_num)] = round(val, 2)'''

new1 = '''        # Значения по месяцам
        for m_str, data in by_month.items():
            m_num = int(m_str.split("-")[1])
            val = data.get(key, 0)
            if key in NEGATIVE:
                val = -abs(val)
            row[mcol(m_num) - 1] = round(val, 2)'''

if old1 in src:
    src = src.replace(old1, new1)
    print("[OK] Месяцы: возвращён -1")
else:
    print("[?] Не нашёл блок месяцев")

old2 = '''    for i, name in enumerate(MONTHS):
        header[mcol(i + 1)] = name
    for i, name in enumerate(QUARTERS):
        header[qcol(i + 1)] = name'''

new2 = '''    for i, name in enumerate(MONTHS):
        header[mcol(i + 1) - 1] = name
    for i, name in enumerate(QUARTERS):
        header[qcol(i + 1) - 1] = name'''

if old2 in src:
    src = src.replace(old2, new2)
    print("[OK] Заголовки: возвращён -1")
else:
    print("[?] Не нашёл блок заголовков")

old3 = '''        row[COL_YEAR] = f"=SUM({c1}{r_num}:{c12}{r_num})"'''
new3 = '''        row[COL_YEAR - 1] = f"=SUM({c1}{r_num}:{c12}{r_num})"'''
if old3 in src:
    src = src.replace(old3, new3)
    print("[OK] Год: возвращён -1")

old4 = '''            row[qcol(q)] = f"=SUM({cA}{r_num}:{cB}{r_num})"'''
new4 = '''            row[qcol(q) - 1] = f"=SUM({cA}{r_num}:{cB}{r_num})"'''
if old4 in src:
    src = src.replace(old4, new4)
    print("[OK] Кварталы: возвращён -1")

open("sync_pnl.py", "w", encoding="utf-8").write(src)
print("\nГотово.")
