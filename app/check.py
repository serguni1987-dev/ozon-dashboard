import sqlite3
import csv

con = sqlite3.connect("ozon.db")

# 1. Общие числа
q1 = "SELECT COUNT(DISTINCT sku) FROM monthly_realization_rows WHERE is_return=0 AND month LIKE '2026-%'"
q2 = "SELECT COUNT(DISTINCT sku) FROM product_cost_history"
print("SKU в realization 2026:", con.execute(q1).fetchone()[0])
print("SKU с cost_price:      ", con.execute(q2).fetchone()[0])

# 2. Суммы по всем статьям — из CSV
total = {
    "revenue": 0.0, "cogs": 0.0, "commission": 0.0,
    "logistics": 0.0, "agents": 0.0, "fbo": 0.0,
    "marketing": 0.0, "tax": 0.0, "margin": 0.0,
}
cats = {"red": 0, "yellow": 0, "green": 0, "grey": 0}

with open("margin_2026.csv", encoding="utf-8-sig") as fh:
    r = csv.reader(fh, delimiter=";")
    header = next(r)
    idx = {name: header.index(name) for name in (
        "Выручка", "Себест", "Комиссия Ozon", "Логистика",
        "Агенты", "FBO", "Маркетинг", "Налог ₽",
        "Маржа ₽", "Маржа %", "Категория"
    )}
    for row in r:
        def num(k):
            try:
                return float(row[idx[k]].replace(",", ".").replace(" ", "").replace("₽", ""))
            except (ValueError, IndexError):
                return 0.0
        total["revenue"]    += num("Выручка")
        total["cogs"]       += num("Себест")
        total["commission"] += num("Комиссия Ozon")
        total["logistics"]  += num("Логистика")
        total["agents"]     += num("Агенты")
        total["fbo"]        += num("FBO")
        total["marketing"]  += num("Маркетинг")
        total["tax"]        += num("Налог ₽")
        total["margin"]     += num("Маржа ₽")
        c = row[idx["Категория"]]
        if c.startswith("🔴"): cats["red"] += 1
        elif c.startswith("🟡"): cats["yellow"] += 1
        elif c.startswith("🟢"): cats["green"] += 1
        else: cats["grey"] += 1

margin_before_tax = total["margin"] + total["tax"]

print()
print("=== Σ по всем SKU за 2026 ===")
print(f"  Выручка            : {total['revenue']:>15,.2f} ₽")
print(f"  Себестоимость      : {total['cogs']:>15,.2f} ₽")
print(f"  Комиссия Ozon      : {total['commission']:>15,.2f} ₽")
print(f"  Логистика          : {total['logistics']:>15,.2f} ₽")
print(f"  Агенты             : {total['agents']:>15,.2f} ₽")
print(f"  FBO                : {total['fbo']:>15,.2f} ₽")
print(f"  Маркетинг          : {total['marketing']:>15,.2f} ₽")
print(f"  Налог              : {total['tax']:>15,.2f} ₽")
print(f"  --------------------------------------------")
print(f"  МАРЖА до налога    : {margin_before_tax:>15,.2f} ₽")
print(f"  МАРЖА после налога : {total['margin']:>15,.2f} ₽")
print()
print(f"  🔴 убыточных   : {cats['red']}")
print(f"  🟡 ниже нормы  : {cats['yellow']}")
print(f"  🟢 норма       : {cats['green']}")
print(f"  ⚪ без выручки : {cats['grey']}")