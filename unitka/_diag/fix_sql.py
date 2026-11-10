import re
from pathlib import Path

path = Path(r"C:\Users\sergu\Desktop\проект\unitka\calc_unit_summary.py")
content = path.read_text(encoding="utf-8")

# Ищем блок SQL от "SELECT" до "GROUP BY r.sku" (игнорируя пробелы и переносы)
pattern = re.compile(r'SELECT\s+COALESCE\(SUM\(r\.sale_price.*?GROUP BY r\.sku', re.DOTALL)
match = pattern.search(content)

if match:
    old_sql = match.group(0)
    new_sql = """SELECT
            COALESCE(SUM(r.sale_price + r.bonus + r.coinvestment), 0) AS revenue,
            COALESCE(SUM(CASE WHEN r.is_return = 0 THEN r.quantity * c.cost_price ELSE 0 END), 0) AS cogs,
            COALESCE(SUM(s.total_exp), 0) AS ozon_exp
        FROM realization_daily r
        LEFT JOIN (
            SELECT sku, cost_price FROM product_cost_history
            WHERE (sku, date_from) IN (SELECT sku, MAX(date_from) FROM product_cost_history GROUP BY sku)
        ) c ON r.sku = c.sku
        LEFT JOIN (
            SELECT sku, date, SUM(ABS(amount)) as total_exp
            FROM accrual_sku_daily
            GROUP BY sku, date
        ) s ON r.sku = s.sku AND r.date = s.date
        GROUP BY r.sku"""
    
    content = content.replace(old_sql, new_sql)
    path.write_text(content, encoding="utf-8")
    print("SUCCESS: SQL успешно обновлен!")
else:
    print("ERROR: Не удалось найти SQL. Возможно, файл уже изменен или структура другая.")