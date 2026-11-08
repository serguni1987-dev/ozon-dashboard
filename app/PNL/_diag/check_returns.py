import sqlite3
c = sqlite3.connect(r"C:\Users\sergu\Desktop\проект\app\ozon.db")
print("month | is_return | n | SUM(sale_price) | MIN | MAX")
for r in c.execute("""
    SELECT month, is_return, COUNT(*),
           ROUND(SUM(sale_price),2),
           ROUND(MIN(sale_price),2),
           ROUND(MAX(sale_price),2)
    FROM monthly_realization_rows
    GROUP BY month, is_return
    ORDER BY month, is_return
"""):
    print(f"  {r[0]} | {r[1]} | {r[2]:>3} | {r[3]:>12} | {r[4]:>10} | {r[5]:>10}")
c.close()