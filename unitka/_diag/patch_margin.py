import re
from pathlib import Path

path = Path(r"C:\Users\sergu\Desktop\проект\unitka\calc_margin.py")
content = path.read_text(encoding="utf-8")

# 1. Добавляем названия колонок в HEADER
old_header = '"Доп. расходы, руб.", "Доп. расходы на ед., руб.",\n]'
new_header = '"Доп. расходы, руб.", "Доп. расходы на ед., руб.",\n    "Мин. цена в ноль, руб.", "Мин. цена с рекламой, руб.", "Запас до мин. цены, руб.",\n]'
if old_header in content:
    content = content.replace(old_header, new_header)

# 2. Достаем минимальные цены из floors и добавляем в словарь s
old_loop = '''    for s in data.values():
        s["tax_rate"] = tax_rate
        s = calc_derived(s)
        if s["orders"] > 0 or s["purchased"] > 0:
            items.append(s)'''
new_loop = '''    for s in data.values():
        s["tax_rate"] = tax_rate
        s = calc_derived(s)
        if s["orders"] > 0 or s["purchased"] > 0:
            # Добавляем мин. цены из floors (которые посчитал unit_core)
            f = floors.get(s["sku"]) or floors.get(str(s["sku"])) or floors.get(s.get("offer_id", "")) or {}
            s["min_price_zero"] = f.get("min_price_zero", f.get("min_price", 0.0))
            s["min_price_ad"] = f.get("min_price_ad", 0.0)
            s["margin_until_min"] = (s.get("price_sale", 0) - s["min_price_zero"]) if s["min_price_zero"] > 0 else 0.0
            items.append(s)'''
if old_loop in content:
    content = content.replace(old_loop, new_loop)

# 3. Записываем новые значения в строки таблицы
old_row = '''            round(s["extras"], 2), round(s["extras_u"], 2),
        ])'''
new_row = '''            round(s["extras"], 2), round(s["extras_u"], 2),
            round(s.get("min_price_zero", 0), 2), round(s.get("min_price_ad", 0), 2), round(s.get("margin_until_min", 0), 2),
        ])'''
if old_row in content:
    content = content.replace(old_row, new_row)

# 4. Настраиваем формат валюты для новых колонок
old_fmt = 'f"AK2:AL{n_rows}", f"AM2:AN{n_rows}", f"AO2:AP{n_rows}", f"AS2:AV{n_rows}"):'
new_fmt = 'f"AK2:AL{n_rows}", f"AM2:AN{n_rows}", f"AO2:AP{n_rows}", f"AS2:AV{n_rows}", f"AW2:AY{n_rows}"):'
if old_fmt in content:
    content = content.replace(old_fmt, new_fmt)

path.write_text(content, encoding="utf-8")
print("УСПЕХ: calc_margin.py обновлен (добавлены 3 колонки с мин. ценами)")