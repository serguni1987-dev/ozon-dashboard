"""
patch_money_verdicts_inline.py — колонка J «Оценка» рядом с маржой.
"""
import re

src = open("sheets_sync.py", encoding="utf-8").read()

# === 1. В build_money добавляем вердикт-функцию и колонку J ===
old_hdr = '''        ["Период", "Выручка", "Себестоимость", "Комиссия", "Услуги Ozon",
         "Прибыль", "Маржа", "Заказов", "Ср. чек"],
    ]

    def calc_period(d1, d2):'''

new_hdr = '''        ["Период", "Выручка", "Себестоимость", "Комиссия", "Услуги Ozon",
         "Прибыль", "Маржа", "Заказов", "Ср. чек", "Оценка"],
    ]

    def verdict(m):
        if m < 0.05:
            return "❌ Убыток"
        if m < 0.10:
            return "⚠ Тонко"
        if m < 0.15:
            return "✅ Норма"
        return "🟢 Отлично"

    def calc_period(d1, d2):'''

if old_hdr in src:
    src = src.replace(old_hdr, new_hdr)
    print("[OK] заголовок с колонкой J")
else:
    print("[?] Не нашёл заголовок периодов")

# === 2. В data.append для периодов — добавляем вердикт ===
old_append = '''        data.append([
            label,
            f"{rev:,.0f}", f"{cost:,.0f}", f"{comm:,.0f}", f"{serv:,.0f}",
            f"{profit:,.0f}", f"{margin*100:.1f}%", orders, f"{avg:,.0f}",
        ])

    # Легенда'''

new_append = '''        data.append([
            label,
            f"{rev:,.0f}", f"{cost:,.0f}", f"{comm:,.0f}", f"{serv:,.0f}",
            f"{profit:,.0f}", f"{margin*100:.1f}%", orders, f"{avg:,.0f}",
            verdict(margin),
        ])

    # Легенда'''

if old_append in src:
    src = src.replace(old_append, new_append)
    print("[OK] вердикт для периодов")
else:
    print("[?] Не нашёл append периодов")

# === 3. Легенда — растянуть на A:J ===
src = src.replace(
    '''        "Маржа = Прибыль / Выручка. Premium — постоянный расход, не в марже.",
        "", "", "", "", "", "", "", ""
    ])''',
    '''        "Маржа = Прибыль / Выручка. Premium — постоянный расход, не в марже.",
        "", "", "", "", "", "", "", "", ""
    ])'''
)

# === 4. Заголовок ПО МЕСЯЦАМ — с колонкой J ===
src = src.replace(
    '''    data.append(["Месяц", "Выручка", "Себестоимость", "Комиссия", "Услуги Ozon",
                 "Прибыль", "Маржа", "Заказов", "Ср. чек"])''',
    '''    data.append(["Месяц", "Выручка", "Себестоимость", "Комиссия", "Услуги Ozon",
                 "Прибыль", "Маржа", "Заказов", "Ср. чек", "Оценка"])'''
)
print("[OK] заголовок месяцев")

# === 5. Append месяцев — с вердиктом ===
old_m = '''        data.append([
            label,
            f"{rev:,.0f}", f"{cost:,.0f}", f"{comm:,.0f}", f"{serv:,.0f}",
            f"{profit:,.0f}", f"{margin*100:.1f}%", orders, f"{avg:,.0f}",
        ])

    data.append(["", "", "", "", "", "", "", "", ""])'''

new_m = '''        data.append([
            label,
            f"{rev:,.0f}", f"{cost:,.0f}", f"{comm:,.0f}", f"{serv:,.0f}",
            f"{profit:,.0f}", f"{margin*100:.1f}%", orders, f"{avg:,.0f}",
            verdict(margin),
        ])

    data.append(["", "", "", "", "", "", "", "", "", ""])'''

if old_m in src:
    src = src.replace(old_m, new_m)
    print("[OK] вердикт для месяцев")
else:
    print("[?] Не нашёл append месяцев")

# === 6. Пустые строки-разделители должны быть на 10 колонок ===
src = src.replace(
    'data.append(["", "", "", "", "", "", "", "", ""])',
    'data.append(["", "", "", "", "", "", "", "", "", ""])'
)
print("[OK] пустые строки 10 колонок")

# === 7. Выводы-строки — тоже 10 колонок ===
for v_var in ["v1", "v2", "v3", "v4", "v5"]:
    src = src.replace(
        f'data.append([{v_var}, "", "", "", "", "", "", "", ""])',
        f'data.append([{v_var}, "", "", "", "", "", "", "", "", ""])'
    )
print("[OK] выводы — 10 колонок")

# Premium
src = src.replace(
    '''    data.append([f"PremiumSubscription {PREMIUM_FIXED:,.0f} ₽/мес — постоянный расход, не в марже",
                 "", "", "", "", "", "", "", ""])''',
    '''    data.append([f"PremiumSubscription {PREMIUM_FIXED:,.0f} ₽/мес — постоянный расход, не в марже",
                 "", "", "", "", "", "", "", "", ""])'''
)
print("[OK] Premium — 10 колонок")

# Заголовок ДЕНЬГИ
src = src.replace(
    '''    data = [
        ["ДЕНЬГИ", "", "", "", "", "", "", "", ""],
        [f"ставки: комиссия {COMMISSION_PCT*100:.2f}%, услуги {SERVICES_PCT*100:.1f}%",
         "", "", "", "", "", "", "", ""],''',
    '''    data = [
        ["ДЕНЬГИ", "", "", "", "", "", "", "", "", ""],
        [f"ставки: комиссия {COMMISSION_PCT*100:.2f}%, услуги {SERVICES_PCT*100:.1f}%",
         "", "", "", "", "", "", "", "", ""],'''
)
print("[OK] заголовок — 10 колонок")

# ============ ОБНОВЛЯЕМ format_money ============
# Меняем все диапазоны с I на J

# Заголовок A1:J1
src = src.replace(
    '    ops.append({"type": "merge", "range": "A1:I1"})\n    ops.append({"type": "format", "range": "A1:I1", "format": FMT_TITLE})',
    '    ops.append({"type": "merge", "range": "A1:J1"})\n    ops.append({"type": "format", "range": "A1:J1", "format": FMT_TITLE})'
)

src = src.replace(
    '    ops.append({"type": "merge", "range": "A2:I2"})\n    ops.append({"type": "format", "range": "A2:I2", "format": sub_fmt})',
    '    ops.append({"type": "merge", "range": "A2:J2"})\n    ops.append({"type": "format", "range": "A2:J2", "format": sub_fmt})'
)

src = src.replace(
    '    ops.append({"type": "format", "range": "A4:I4", "format": tbl_hdr})',
    '    ops.append({"type": "format", "range": "A4:J4", "format": tbl_hdr})'
)

# Данные периодов B:F, G (маржа), H:I → H:J
src = src.replace(
    '''    for r in range(5, 8):
        ops.append({"type": "format", "range": f"A{r}", "format": body_label})
        ops.append({"type": "format", "range": f"B{r}:F{r}", "format": body_money})
        ops.append({"type": "format", "range": f"G{r}", "format": body_margin})
        ops.append({"type": "format", "range": f"H{r}:I{r}", "format": body_center})
        ops.append({"type": "row_height", "row": r, "height": 32})''',
    '''    verdict_fmt = CellFormat(
        textFormat=TextFormat(fontSize=11, bold=True),
        horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
    )
    for r in range(5, 8):
        ops.append({"type": "format", "range": f"A{r}", "format": body_label})
        ops.append({"type": "format", "range": f"B{r}:F{r}", "format": body_money})
        ops.append({"type": "format", "range": f"G{r}", "format": body_margin})
        ops.append({"type": "format", "range": f"H{r}:I{r}", "format": body_center})
        ops.append({"type": "format", "range": f"J{r}", "format": verdict_fmt})
        ops.append({"type": "row_height", "row": r, "height": 32})'''
)

# Легенда A8:I8 → A8:J8
src = src.replace(
    '    ops.append({"type": "merge", "range": "A8:I8"})\n    ops.append({"type": "format", "range": "A8:I8", "format": legend_fmt})',
    '    ops.append({"type": "merge", "range": "A8:J8"})\n    ops.append({"type": "format", "range": "A8:J8", "format": legend_fmt})'
)

# ПО МЕСЯЦАМ A10:I10 → A10:J10
src = src.replace(
    '    ops.append({"type": "merge", "range": "A10:I10"})\n    ops.append({"type": "format", "range": "A10:I10", "format": FMT_SUBHEADER})',
    '    ops.append({"type": "merge", "range": "A10:J10"})\n    ops.append({"type": "format", "range": "A10:J10", "format": FMT_SUBHEADER})'
)

# Заголовки месяцев A11:I11 → A11:J11
src = src.replace(
    '    ops.append({"type": "format", "range": "A11:I11", "format": tbl_hdr})',
    '    ops.append({"type": "format", "range": "A11:J11", "format": tbl_hdr})'
)

# Данные месяцев 12-15 — добавляем J
src = src.replace(
    '''    for r in range(12, 16):
        ops.append({"type": "format", "range": f"A{r}", "format": body_label})
        ops.append({"type": "format", "range": f"B{r}:F{r}", "format": body_money})
        ops.append({"type": "format", "range": f"G{r}", "format": body_margin})
        ops.append({"type": "format", "range": f"H{r}:I{r}", "format": body_center})
        ops.append({"type": "row_height", "row": r, "height": 32})''',
    '''    for r in range(12, 16):
        ops.append({"type": "format", "range": f"A{r}", "format": body_label})
        ops.append({"type": "format", "range": f"B{r}:F{r}", "format": body_money})
        ops.append({"type": "format", "range": f"G{r}", "format": body_margin})
        ops.append({"type": "format", "range": f"H{r}:I{r}", "format": body_center})
        ops.append({"type": "format", "range": f"J{r}", "format": verdict_fmt})
        ops.append({"type": "row_height", "row": r, "height": 32})'''
)

# ВЫВОДЫ A17:I17 → A17:J17
src = src.replace(
    '    ops.append({"type": "merge", "range": "A17:I17"})\n    ops.append({"type": "format", "range": "A17:I17", "format": FMT_SUBHEADER})',
    '    ops.append({"type": "merge", "range": "A17:J17"})\n    ops.append({"type": "format", "range": "A17:J17", "format": FMT_SUBHEADER})'
)

# Выводы 18-22 A:I → A:J
src = src.replace(
    '        ops.append({"type": "merge", "range": f"A{r}:I{r}"})',
    '        ops.append({"type": "merge", "range": f"A{r}:J{r}"})'
)

# Premium A24:I24 → A24:J24
src = src.replace(
    '    ops.append({"type": "merge", "range": "A24:I24"})\n    ops.append({"type": "format", "range": "A24:I24", "format": premium_fmt})',
    '    ops.append({"type": "merge", "range": "A24:J24"})\n    ops.append({"type": "format", "range": "A24:J24", "format": premium_fmt})'
)

# Ширина J
src = src.replace(
    '    ops.append({"type": "width", "col": "I", "width": 120})',
    '    ops.append({"type": "width", "col": "I", "width": 120})\n    ops.append({"type": "width", "col": "J", "width": 130})'
)

# Цвет выводов A18:A22 → A18:J22 (range расширить)
src = src.replace(
    '            ops3.append({"type": "format", "range": f"A{r}:I{r}", "format": CellFormat(',
    '            ops3.append({"type": "format", "range": f"A{r}:J{r}", "format": CellFormat('
)

open("sheets_sync.py", "w", encoding="utf-8").write(src)
print("[OK] format_money обновлён под 10 колонок")
print("\nГотово. Запускай: py sheets_sync.py")
