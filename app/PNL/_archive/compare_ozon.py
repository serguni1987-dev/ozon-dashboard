"""compare_ozon.py — сравнение наших данных с эталоном Ozon (Сводка).
Группирует accruals_services по логике Ozon Seller и сверяет с эталоном
за янв-май 2026 (данные из скриншотов Ozon Seller → Сводка).
"""
import sqlite3

c = sqlite3.connect("ozon.db")

# ── Эталон Ozon (из дашборда Ozon Seller → Сводка) ──
OZON = {
    "2026-01": {"rashody": 258395.10, "dRR": 69855.99, "sebest": 147966.00, "nalog": 14113.78,
                "commission": 168655.42, "logistic": 44984.26,
                "agents": 7544.85, "fbo": 5490.75, "other": 31719.82},
    "2026-02": {"rashody": 134574.05, "dRR": 45999.74, "sebest": 104799.00, "nalog": 10549.95,
                "commission": 103478.18, "logistic": 21950.05,
                "agents": 5182.71, "fbo": 1764.60, "other": 2198.51},
    "2026-03": {"rashody": 62957.97, "dRR": 48411.25, "sebest": 44239.00, "nalog": 5049.27,
                "commission": 47112.73, "logistic": 7594.85,
                "agents": 1707.94, "fbo": 4630.90, "other": 1911.55},
    "2026-04": {"rashody": 52118.94, "dRR": 6847.79, "sebest": 28084.00, "nalog": 2862.33,
                "commission": 38450.85, "logistic": 6602.92,
                "agents": 1575.66, "fbo": 4781.75, "other": 707.76},
    "2026-05": {"rashody": 45646.87, "dRR": 18081.96, "sebest": 30861.00, "nalog": 2319.31,
                "commission": 28996.68, "logistic": 4046.00,
                "agents": 1876.48, "fbo": 9388.75, "other": 1338.96},
}

# ── Наша группировка (по логике Ozon) ──
GROUPS = {
    "logistic": [32, 59, 98, 16],                   # Logistic, ReturnFlow, DeliveryToHandover, Drop-Off
    "agents":   [1, 74, 29, 45],                    # Acquiring, Stars, LastMile, PickUp
    "fbo":      [46, 71, 76, 12, 77],               # Placements, SellerReturns, StockInsurance, CrossDock, SupplyInbound
    "other":    [14, 15, 48, 52, 93, 94, 78, 79],   # DefectRate, Disposal, Premium*, Temp*
    "dRR":      [41, 54, 3, 47, 96],                # PayPerClick, Promotion, BrandCommission, PointsForReviews, AcceleratedReview
}

MONTHS = ["2026-01","2026-02","2026-03","2026-04","2026-05"]
SHORT  = ["янв","фев","мар","апр","май"]


def service_sum(month, type_ids):
    if not type_ids:
        return 0.0
    ids = ",".join(map(str, type_ids))
    q = (f"SELECT SUM(ABS(amount)) FROM accruals_services "
         f"WHERE date >= '{month}-01' AND date <= '{month}-31' "
         f"AND type_id IN ({ids})")
    return c.execute(q).fetchone()[0] or 0.0


def commission(month):
    r = c.execute("SELECT SUM(gross_commission) FROM monthly_realization_rows WHERE month = ?",
                  (month,)).fetchone()
    return r[0] or 0.0


print("=" * 80)
print("СРАВНЕНИЕ: НАШИ ДАННЫЕ vs ЭТАЛОН OZON (янв-май 2026)")
print("=" * 80)

for label, key in [
    ("Комиссия Ozon", "commission"),
    ("Логистика", "logistic"),
    ("Услуги агентов", "agents"),
    ("Услуги FBO", "fbo"),
    ("Другие услуги", "other"),
    ("Реклама (ДРР)", "dRR"),
]:
    print(f"\n### {label}")
    print(f"{'Мес':<5} | {'Ozon':>11} | {'Наше':>11} | {'Разница':>11} | {'Δ%':>6}")
    print("-" * 60)
    for m, s in zip(MONTHS, SHORT):
        oz = OZON[m][key]
        our = commission(m) if key == "commission" else service_sum(m, GROUPS[key])
        diff = our - oz
        pct = (diff / oz * 100) if oz else 0
        mark = "⚠" if abs(diff) > 500 else "✓"
        print(f"{s:<5} | {oz:>11,.2f} | {our:>11,.2f} | {diff:>+11,.2f} | {pct:>+5.1f}% {mark}")

print("\n" + "=" * 80)
print("ИТОГО РАСХОДЫ (Комиссия + Логистика + Агенты + FBO + Другие)")
print("=" * 80)
print(f"{'Мес':<5} | {'Ozon':>11} | {'Наше':>11} | {'Разница':>11}")
print("-" * 55)
for m, s in zip(MONTHS, SHORT):
    oz = OZON[m]["rashody"]
    our = (commission(m)
           + service_sum(m, GROUPS["logistic"])
           + service_sum(m, GROUPS["agents"])
           + service_sum(m, GROUPS["fbo"])
           + service_sum(m, GROUPS["other"]))
    diff = our - oz
    mark = "⚠" if abs(diff) > 500 else "✓"
    print(f"{s:<5} | {oz:>11,.2f} | {our:>11,.2f} | {diff:>+11,.2f} {mark}")

print()
print("⚠ = расхождение больше 500 ₽")
print("✓ = в пределах 500 ₽ (норма — это округления Ozon + наши type_id)")

c.close()