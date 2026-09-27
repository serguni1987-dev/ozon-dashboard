"""
compare_services.py - сравнение услуг из accruals_services с приложением.
"""
import os
import sqlite3

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(APP_DIR, "ozon.db")

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

print("=" * 100)
print("УСЛУГИ OZON ЗА АВГУСТ 2026 — СРАВНЕНИЕ С ПРИЛОЖЕНИЕМ")
print("=" * 100)

# Все услуги по типам
rows = con.execute("""
    SELECT type_id, type_name,
           SUM(amount) AS total,
           COUNT(*) AS n
    FROM accruals_services
    WHERE date >= '2026-08-01' AND date < '2026-09-01'
    GROUP BY type_id, type_name
    ORDER BY ABS(SUM(amount)) DESC
""").fetchall()

print(f"\n{'Type ID':<8} {'Название':<40} {'Сумма':>14} {'Записей':>8}")
print("-" * 80)
total_all = 0
for r in rows:
    print(f"{r['type_id']:<8} {r['type_name']:<40} {r['total']:>14,.2f} {r['n']:>8}")
    total_all += r['total']
print("-" * 80)
print(f"{'ИТОГО':<49} {total_all:>14,.2f}")

# === Группировка по приложению ===
print(f"\n\n{'='*100}")
print("ПОПЫТКА СГРУППИРОВАТЬ ПО КАТЕГОРИЯМ ПРИЛОЖЕНИЯ")
print("=" * 100)

# Собираем всё в dict
services = {r['type_name']: r['total'] for r in rows}

def get(*names):
    """Сумма по списку названий."""
    return sum(services.get(n, 0) for n in names)

# Гипотезы группировки
print(f"\n[ЛОГИСТИКА] — приложение: 9 850,00")
logist = get("Logistic", "ReturnFlowLogistic", "LastMileCourier",
             "DeliveryToHandoverPlaceByOzon", "LastMile")
print(f"  Logistic + ReturnFlowLogistic + LastMileCourier + DeliveryToHandoverPlaceByOzon")
print(f"  = {logist:,.2f}  (Δ от 9850: {logist - 9850:+,.2f})")

print(f"\n[УСЛУГИ АГЕНТОВ] — приложение: 9 028,22")
agent_variants = [
    ("EarlyPayment",),
    ("EarlyPayment", "FlexiblePayments"),
    ("EarlyPayment", "FlexiblePayments", "PayPerClick"),
    ("RfbsDomesticAgentFee", "RfbsGlobalAgentFee"),
]
for names in agent_variants:
    val = get(*names)
    print(f"  {' + '.join(names):<60} = {val:>12,.2f}  (Δ: {val - 9028.22:+,.2f})")

print(f"\n[УСЛУГИ FBO] — приложение: 721,00")
print(f"  Fulfillment:                   {get('Fulfillment'):>12,.2f}")
print(f"  Shipment:                      {get('Shipment'):>12,.2f}")
print(f"  StockInsurance:                {get('StockInsurance'):>12,.2f}")
print(f"  TemporaryPlacement:            {get('TemporaryPlacement'):>12,.2f}")
print(f"  PreparingToReturn:             {get('PreparingToReturn'):>12,.2f}")
print(f"  CrossDock:                     {get('CrossDock'):>12,.2f}")
print(f"  ReturnStorageInTheWarehouse:   {get('ReturnStorageInTheWarehouse'):>12,.2f}")
print(f"  Disposal:                      {get('Disposal'):>12,.2f}")
print(f"  Marking:                       {get('Marking'):>12,.2f}")

print(f"\n[ДРУГИЕ УСЛУГИ И ШТРАФЫ] — приложение: 391,50")
fines = get("DefectFineErrors", "DefectFineModeration",
            "DefectFineProhibitedGoods", "DefectFineCounterfeitGoods",
            "DefectFineComplaint", "DefectFineShipmentDelayRate",
            "DefectRate")
print(f"  Все DefectFine*:               {fines:>12,.2f}")

print(f"\n[КОМПЕНСАЦИИ] — приложение: 0,00")
comp = get("Compensation", "ItemCompensation", "B2CInsuranceCompensation")
print(f"  Compensation*:                 {comp:>12,.2f}")

print(f"\n[ПРОЧИЕ НАЧИСЛЕНИЯ] — приложение: 4 686,10")
other = get("EarlyPayment", "FlexiblePayments")
print(f"  EarlyPayment + FlexiblePayments: {other:>12,.2f}  (Δ: {other - 4686.10:+,.2f})")
other2 = get("EarlyPayment", "FlexiblePayments", "PayPerClick",
             "Marketing", "Promotion", "ExternalPromotion")
print(f"  + маркетинг:                   {other2:>12,.2f}")

print(f"\n\n{'='*100}")
print("СВОДКА — ЧТО ПРИЛОЖЕНИЕ СЧИТАЕТ (СУММА 175 726,91)")
print("=" * 100)
app = [
    ("Комиссия Ozon", 151050.09),
    ("Логистика", 9850),
    ("Услуги агентов", 9028.22),
    ("Услуги FBO", 721),
    ("Другие услуги и штрафы", 391.5),
    ("Компенсации", 0),
    ("Прочие начисления", 4686.1),
]
total_app = sum(v for _, v in app)
for name, val in app:
    print(f"  {name:<30} {val:>14,.2f}")
print(f"  {'ИТОГО':<30} {total_app:>14,.2f}")

# Мы показываем все наши услуги
print(f"\n\n[НАШИ УСЛУГИ ВСЕГО]: {total_all:,.2f}")
print(f"Приложение показывает только часть (175 726,91 включает комиссию 151 050).")
print(f"Услуги без комиссии в приложении: {total_app - 151050.09:,.2f}")
print(f"У нас всего услуг (без комиссии):  {total_all:,.2f}")
print(f"Разница:                           {total_all - (total_app - 151050.09):+,.2f}")

con.close()
