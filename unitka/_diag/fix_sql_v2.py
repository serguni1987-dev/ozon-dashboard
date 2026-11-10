from pathlib import Path

path = Path(r"C:\Users\sergu\Desktop\проект\unitka\calc_unit_summary.py")
content = path.read_text(encoding="utf-8")

# 1. Меняем расчет расходов на предварительно сгруппированный
old_exp = 'COALESCE(SUM(ABS(s.amount)), 0) AS ozon_exp'
new_exp = 'COALESCE(SUM(s.total_exp), 0) AS ozon_exp'

# 2. Меняем сам JOIN на подзапрос, чтобы не было дублей
old_join = 'LEFT JOIN accrual_sku_daily s ON r.sku = s.sku AND r.date = s.date'
new_join = 'LEFT JOIN (SELECT sku, date, SUM(ABS(amount)) as total_exp FROM accrual_sku_daily GROUP BY sku, date) s ON r.sku = s.sku AND r.date = s.date'

changed = False
if old_exp in content:
    content = content.replace(old_exp, new_exp)
    changed = True
if old_join in content:
    content = content.replace(old_join, new_join)
    changed = True

if changed:
    path.write_text(content, encoding="utf-8")
    print("SUCCESS: SQL в calc_unit_summary.py успешно исправлен!")
else:
    print("ERROR: Не удалось найти нужные строки. Пришлите текст функции.")