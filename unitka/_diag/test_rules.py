from unitka.rules import evaluate_sku
import sqlite3
from unitka import config

con = sqlite3.connect(str(config.DB_PATH))
con.row_factory = sqlite3.Row
cur = con.cursor()

# Берем один SKU из Юнит-сводки
cur.execute("""
    SELECT r.sku, SUM(r.sale_price) as revenue, SUM(r.quantity) as qty
    FROM realization_daily r
    WHERE r.sku = '1605108599'
    GROUP BY r.sku
""")
row = cur.fetchone()
if row:
    sku = str(row["sku"])
    # Собираем "паспорт" этого SKU (имитация)
    sku_data = {
        "sku": sku,
        "offer_id": "OCE013E4",
        "price": 11802, # Выручка за шт (пример)
        "min_price": 15269, # Мин цена (из аудита)
        "stock": 2, # Остаток
        "sold_14d": 4, # Продажи за 14 дней
        "avg_price": 5901,
        "cost": 85392, 
        "margin_pct": -674.6, # Маржа
        "revenue_30d": 11802
    }
    
    tasks = evaluate_sku(sku_data)
    print(f"=== ТЕСТ ПРАВИЛ ДЛЯ SKU {sku} ({sku_data['offer_id']}) ===")
    if not tasks:
        print("Проблем не найдено.")
    for t in tasks:
        sev = "🔴" if t.severity == 1 else ("🟡" if t.severity == 2 else "🟢")
        print(f"{sev} [{t.rule_id}] {t.problem}")
        print(f"   → {t.action}")
        print(f"   💰 Эффект: {t.money_impact:,.0f} ₽\n")
else:
    print("SKU не найден в базе")

con.close()