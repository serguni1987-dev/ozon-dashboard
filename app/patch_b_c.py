"""patch_b_c: заголовок C, пропуск % для справочных строк, больше вердиктов, стили C и T."""
import shutil, re
from datetime import datetime

# ─── 1. sync_pnl.py ───
SRC = "PNL/sync_pnl.py"
bak = f"{SRC}.bak-bc-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
shutil.copy(SRC, bak)
print(f"Бэкап 1: {bak}")

src = open(SRC, encoding="utf-8").read()

# 1.1 Обновляем make_verdict — расширенный
m = re.search(r"def make_verdict\(.*?\n    return \"\"", src, re.DOTALL)
if not m:
    print("[?] не найден make_verdict")
    raise SystemExit(1)

new_verdict = '''def make_verdict(label, pct_signed):
    """Текстовый вердикт для колонки T."""
    lbl = label.strip().lower()

    # ── родительские суммы ──
    if "фулфилмент" in lbl and ":" in label:
        pct = abs(pct_signed)
        if pct <= 8: return "✓ норма"
        if pct <= 12: return "⚠ высоко"
        return "!! критично"
    if "маркетинг" in lbl and ":" in label:
        pct = abs(pct_signed)
        if pct <= 10: return "✓ норма"
        if pct <= 15: return "⚠ высоко"
        return "!! критично"
    if "прямые" in lbl and "расход" in lbl:
        pct = abs(pct_signed)
        if pct <= 60: return "✓ норма"
        if pct <= 75: return "⚠ высоко"
        return "!! критично"

    # ── маржинальные ──
    if "валовая прибыль" in lbl or "чистая прибыль" in lbl or "ebitda" in lbl:
        if pct_signed >= 20: return "✓ норма"
        if pct_signed >= 10: return "⚠ средне"
        if pct_signed >= 0:  return "⚠ низко"
        return "!! убыток"
    if "доходы" in lbl and ":" not in label:
        return "✓ база"

    # ── баллы и партнёрские — не расходы ──
    if "баллы" in lbl and "начислено" not in lbl:
        return "✓ компенсация"
    if "программы партнёров" in lbl:
        return "✓ партнёрские"

    # ── расходные ──
    pct = abs(pct_signed)
    if "комиссия" in lbl:
        if pct <= 45: return "✓ норма"
        if pct <= 55: return "⚠ высоко"
        return "!! критично"
    if "логистика" in lbl and "обратная" not in lbl:
        if pct <= 8: return "✓ норма"
        if pct <= 12: return "⚠ высоко"
        return "!! критично"
    if "себестоимость" in lbl:
        if pct <= 35: return "✓ норма"
        if pct <= 45: return "⚠ высоко"
        return "!! критично"
    if "реклама" in lbl:
        if pct <= 10: return "✓ норма"
        if pct <= 15: return "⚠ высоко"
        return "!! критично"
    if "fbo" in lbl:
        if pct <= 3: return "✓ норма"
        if pct <= 5: return "⚠ высоко"
        return "!! критично"
    if "другие услуги" in lbl or "прочие" in lbl:
        if pct <= 1: return "✓ норма"
        if pct <= 3: return "⚠ мелкие штрафы"
        return "!! штрафы"
    return ""'''

src = src[:m.start()] + new_verdict + src[m.end():]
print("[OK] make_verdict обновлён")

# 1.2 Заголовок C
src = src.replace('    row2[2] = "%"\n', '    row2[2] = "% от базы"\n')
print("[OK] заголовок C: '% от базы'")

# 1.3 Пропуск % для строк «Заказы» и «Начислено баллов»
old_calc = '''        row[COL_YEAR - 1] = f"=SUM({c1}{r_num}:{c12}{r_num})"
        row[COL_PCT - 1] = f"=IF($B$5=0;0;B{r_num}/$B$5*100)"'''
new_calc = '''        row[COL_YEAR - 1] = f"=SUM({c1}{r_num}:{c12}{r_num})"
        skip_pct = label.strip().lower() in ("заказы (справочно)", "начислено баллов")
        if not skip_pct:
            row[COL_PCT - 1] = f"=IF($B$5=0;0;B{r_num}/$B$5*100)"'''
if old_calc in src:
    src = src.replace(old_calc, new_calc)
    print("[OK] пропуск % для справочных строк")
else:
    print("[?] не найден блок calc %")

open(SRC, "w", encoding="utf-8").write(src)
print()

# ─── 2. pnl_format.py — стили C и T + условное форматирование ───
SRC2 = "PNL/pnl_format.py"
bak2 = f"{SRC2}.bak-bc-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
shutil.copy(SRC2, bak2)
print(f"Бэкап 2: {bak2}")

src2 = open(SRC2, encoding="utf-8").read()

# 2.1 Добавить ORANGE_FG (если нет)
if "ORANGE_FG" not in src2:
    src2 = src2.replace(
        'RED_FG=rgb("7F0000"); BORDER=rgb("BFBFBF")',
        'RED_FG=rgb("7F0000"); ORANGE_FG=rgb("7F3F00"); BORDER=rgb("BFBFBF")'
    )
    print("[OK] добавлен ORANGE_FG")

# 2.2 Цвета для колонки C — серая, italic
anchor = '''    # родители без фона
    for r in (16,21,36):'''
add_c = '''    # колонка C — узкая, серая, italic
    reqs.append({"repeatCell":{"range":grid(sid,2,N,2,3),
        "cell":{"userEnteredFormat":cell(bg=WHITE,fg=GREY_TXT,italic=True,size=10)},
        "fields":"userEnteredFormat"}})
    # колонка T — серая, italic, align LEFT
    reqs.append({"repeatCell":{"range":grid(sid,2,N,19,20),
        "cell":{"userEnteredFormat":cell(bg=WHITE,fg=GREY_TXT,italic=True,size=10,align="LEFT")},
        "fields":"userEnteredFormat"}})

    # родители без фона
    for r in (16,21,36):'''
if anchor in src2:
    src2 = src2.replace(anchor, add_c, 1)
    print("[OK] стили C и T добавлены")

# 2.3 Ширины: C=75, T=115, остальные 85 (без C и T)
old_w = '''    for i in range(2,19):
        reqs.append({"updateDimensionProperties":{"range":{"sheetId":sid,"dimension":"COLUMNS","startIndex":i,"endIndex":i+1},
            "properties":{"pixelSize":85},"fields":"pixelSize"}})'''
new_w = '''    for i in range(3,19):
        reqs.append({"updateDimensionProperties":{"range":{"sheetId":sid,"dimension":"COLUMNS","startIndex":i,"endIndex":i+1},
            "properties":{"pixelSize":85},"fields":"pixelSize"}})
    reqs.append({"updateDimensionProperties":{"range":{"sheetId":sid,"dimension":"COLUMNS","startIndex":2,"endIndex":3},
        "properties":{"pixelSize":75},"fields":"pixelSize"}})
    reqs.append({"updateDimensionProperties":{"range":{"sheetId":sid,"dimension":"COLUMNS","startIndex":19,"endIndex":20},
        "properties":{"pixelSize":115},"fields":"pixelSize"}})'''
if old_w in src2:
    src2 = src2.replace(old_w, new_w)
    print("[OK] ширины C и T настроены")
else:
    print("[?] не найден блок ширин")

# 2.4 Формат чисел: C — проценты, не RUB
anchor2 = '''    reqs.append({"repeatCell":{"range":grid(sid,2,N,1,20),
        "cell":{"userEnteredFormat":{"numberFormat":{"type":"NUMBER","pattern":NUM}}},
        "fields":"userEnteredFormat.numberFormat"}})'''
add_c_fmt = anchor2 + '''
    # C — проценты
    reqs.append({"repeatCell":{"range":grid(sid,2,N,2,3),
        "cell":{"userEnteredFormat":{"numberFormat":{"type":"NUMBER","pattern":'0.00" %"'}}},
        "fields":"userEnteredFormat.numberFormat"}})'''
if anchor2 in src2:
    src2 = src2.replace(anchor2, add_c_fmt, 1)
    print("[OK] формат числа C = %")

# 2.5 Условное форматирование для T
anchor3 = '''    # границы
    reqs.append({"updateBorders":{"range":grid(sid,0,1),'''
cond_format = '''    # условное форматирование T (приоритет — первый)
    for prefix, bg, fg in [
        ("!!", RED_BG, RED_FG),
        ("⚠", ORANGE_BG, ORANGE_FG),
        ("✓", GREEN_BG, GREEN_FG),
    ]:
        reqs.append({"addConditionalFormatRule":{
            "rule":{
                "ranges":[grid(sid,2,N,19,20)],
                "booleanRule":{
                    "condition":{"type":"TEXT_STARTS_WITH",
                                 "values":[{"userEnteredValue":prefix}]},
                    "format":{"backgroundColor":bg,
                              "textFormat":{"foregroundColor":fg,"bold":True}}
                }
            },
            "index":0
        }})

    # границы
    reqs.append({"updateBorders":{"range":grid(sid,0,1),'''
if anchor3 in src2:
    src2 = src2.replace(anchor3, cond_format, 1)
    print("[OK] условное форматирование T")
else:
    print("[?] не найден anchor границ")

open(SRC2, "w", encoding="utf-8").write(src2)
print()

print("Готово. Пересинкай:")
print("  py PNL\\sync_pnl.py 2026")
print("  py PNL\\pnl_format.py")
print("  py PNL\\fix_sheet_full.py")
