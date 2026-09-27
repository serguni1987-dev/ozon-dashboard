"""patch2: перезаписывает CATEGORY_MAP и GROUPS+service_sum в compare_ozon.py."""
import os, shutil, re
from datetime import datetime

# ── 1. sync_pnl.py: заменить весь CATEGORY_MAP ──
SRC1 = "PNL/sync_pnl.py"
bak1 = f"{SRC1}.bak2-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
shutil.copy(SRC1, bak1)
print(f"Бэкап 1: {bak1}")

src = open(SRC1, encoding="utf-8").read()
m = re.search(r"CATEGORY_MAP = \{.*?\n\}", src, re.DOTALL)
if not m:
    print("НЕ найден блок CATEGORY_MAP")
    raise SystemExit(1)

new_block = '''CATEGORY_MAP = {
    # фулфилмент (Ozon «Услуги доставки»)
    32: "Логистика", 77: "Логистика", 59: "Логистика",
    45: "Обратная логистика", 29: "Последняя миля", 98: "Последняя миля",
    25: "ItemCompensation",
    12: "Услуги FBO", 16: "Логистика", 17: "Логистика",
    38: "Обработка, сборка", 39: "Обработка, сборка", 71: "Услуги FBO",
    # маркетинг (Ozon «Продвижение и реклама»)
    41: "Реклама PPC", 54: "Продвижение", 3: "Бренд-комиссия",
    47: "Отзывы", 96: "Отзывы",
    22: "Реклама PPC", 52: "Реклама PPC",
    # агенты (Ozon «Услуги партнёров»)
    1:  "Услуги агентов", 74: "Услуги агентов", 79: "Услуги агентов",
    # FBO (Ozon «Услуги FBO»)
    46: "Услуги FBO", 76: "Услуги FBO",
    # другие услуги и штрафы (Ozon)
    14: "Другие услуги", 15: "Другие услуги", 18: "Другие услуги",
    20: "Другие услуги", 48: "Другие услуги", 78: "Другие услуги",
    93: "Другие услуги", 94: "Другие услуги",
    # прочие
    6: "Прочие", 9: "Прочие", 40: "Прочие",
}'''

src = src[:m.start()] + new_block + src[m.end():]
open(SRC1, "w", encoding="utf-8").write(src)
print("[OK] CATEGORY_MAP перезаписан")

# ── 2. compare_ozon.py: заменить GROUPS и service_sum ──
SRC2 = "PNL/_diag/compare_ozon.py"
if not os.path.exists(SRC2):
    print(f"Не найден {SRC2}")
    raise SystemExit(0)

bak2 = f"{SRC2}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
shutil.copy(SRC2, bak2)
print(f"Бэкап 2: {bak2}")

src2 = open(SRC2, encoding="utf-8").read()

old_g = '''GROUPS = {
    "logistic": [32, 59, 98, 16],                   # Logistic, ReturnFlow, DeliveryToHandover, Drop-Off
    "agents":   [1, 74, 29, 45],                    # Acquiring, Stars, LastMile, PickUp
    "fbo":      [46, 71, 76, 12, 77],               # Placements, SellerReturns, StockInsurance, CrossDock, SupplyInbound
    "other":    [14, 15, 48, 52, 93, 94, 78, 79],   # DefectRate, Disposal, Premium*, Temp*
    "dRR":      [41, 54, 3, 47, 96],                # PayPerClick, Promotion, BrandCommission, PointsForReviews, AcceleratedReview
}'''

new_g = '''GROUPS = {
    "logistic": [32, 59, 98, 16, 17, 45, 29, 38, 39, 25],
    "agents":   [1, 74, 79],
    "fbo":      [46, 71, 76, 12, 77],
    "other":    [14, 15, 18, 20, 48, 78, 93, 94],
    "dRR":      [41, 54, 3, 47, 96, 22, 52],
}'''

if old_g in src2:
    src2 = src2.replace(old_g, new_g)
    print("[OK] GROUPS обновлён")
else:
    print("[?] НЕ найден блок GROUPS")

old_ss = '''    q = (f"SELECT SUM(ABS(amount)) FROM accruals_services "
         f"WHERE date >= '{month}-01' AND date <= '{month}-31' "
         f"AND type_id IN ({ids})")
    return c.execute(q).fetchone()[0] or 0.0'''

new_ss = '''    q = (f"SELECT SUM(amount) FROM accruals_services "
         f"WHERE date >= '{month}-01' AND date <= '{month}-31' "
         f"AND type_id IN ({ids})")
    return abs(c.execute(q).fetchone()[0] or 0.0)'''

if old_ss in src2:
    src2 = src2.replace(old_ss, new_ss)
    print("[OK] service_sum обновлён на signed")
else:
    print("[?] НЕ найден блок service_sum")

open(SRC2, "w", encoding="utf-8").write(src2)
print()
print("[OK] Готово")
