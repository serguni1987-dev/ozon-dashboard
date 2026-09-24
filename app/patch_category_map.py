import re
src = open("sync_pnl.py", encoding="utf-8").read()

NEW_MAP = '''CATEGORY_MAP = {
    # ── Озон фулфилмент ────────────────────────────────
    # логистика (стр. 17)
    32: "Логистика",           # Logistic
    77: "Логистика",           # SupplyInbound
    # обратная логистика (стр. 18)
    59: "Обратная логистика",  # ReturnFlowLogistic
    45: "Обратная логистика",  # PickUpPointReturnAcceptance
    71: "Обратная логистика",  # SellerReturns
    # последняя миля (стр. 19)
    29: "Последняя миля",      # LastMileCourier
    98: "Последняя миля",      # DeliveryToHandoverPlaceByOzon
    # обработка, сборка (стр. 20)
    12: "Обработка, сборка",   # CrossDock
    16: "Обработка, сборка",   # Drop-Off
    38: "Обработка, сборка",   # PackageCost
    39: "Обработка, сборка",   # PackingFee
    78: "Обработка, сборка",   # TemporaryPlacement
    79: "Обработка, сборка",   # TemporaryPlacementsAgent

    # ── Озон маркетинг ────────────────────────────────
    41: "Реклама",             # PayPerClick
    54: "Реклама",             # Promotion
    74: "Реклама",             # StarsMembership
    3:  "Реклама",             # BrandCommission
    47: "Отзывы",              # PointsForReviews
    96: "Отзывы",              # AcceleratedReviewCollection

    # ── Услуги агентов ────────────────────────────────
    1:  "Услуги агентов",      # Acquiring
    18: "Услуги агентов",      # EarlyPayment
    20: "Услуги агентов",      # FlexiblePayments
    22: "Услуги агентов",      # Installment

    # ── Услуги FBO ────────────────────────────────────
    46: "Услуги FBO",          # Placements
    76: "Услуги FBO",          # StockInsurance

    # ── Другие услуги ────────────────────────────────
    14: "Другие услуги",       # DefectRate
    15: "Другие услуги",       # Disposal
    48: "Другие услуги",       # PremiumCashbackIndividualPoints
    52: "Другие услуги",       # PremiumSubscription
    93: "Другие услуги",       # DefectFineErrors
    94: "Другие услуги",       # DefectFineShipmentDelayRate

    # ── Прочие ────────────────────────────────────────
    6:  "Прочие",              # Cancellation
    9:  "Прочие",              # ClientReturn
    40: "Прочие",              # PartialReturn
}
'''

m = re.search(r'CATEGORY_MAP\s*=\s*\{[^}]+\}', src, re.DOTALL)
if m:
    src = src[:m.start()] + NEW_MAP + src[m.end():]
    print("[OK] CATEGORY_MAP заменён")
else:
    print("[?] Не нашёл CATEGORY_MAP")

# Переименовать ключ logistics → fulfil_logistics для строки 17
old = '"cogs": cogs, "logistics": cats.get("Логистика", 0),'
new = '"cogs": cogs, "fulfil_logistics": cats.get("Логистика", 0),'
if old in src:
    src = src.replace(old, new, 1); print("[OK] logistics → fulfil_logistics")
else:
    print("[?] Не нашёл logistics в return")

# Добавить fulfil_total
old2 = '"fulfil_reverse":    cats.get("Обратная логистика", 0),'
new2 = ('"fulfil_total":      (cats.get("Логистика", 0)\n'
        '                              + cats.get("Обратная логистика", 0)\n'
        '                              + cats.get("Последняя миля", 0)\n'
        '                              + cats.get("Обработка, сборка", 0)),\n'
        '        "fulfil_reverse":    cats.get("Обратная логистика", 0),')
if old2 in src:
    src = src.replace(old2, new2, 1); print("[OK] fulfil_total добавлен")
else:
    print("[?] Не нашёл fulfil_reverse")

# Строка 16: logistics → fulfil_total
old3 = '("  Озон фулфилмент:", "logistics"),'
new3 = '("  Озон фулфилмент:", "fulfil_total"),'
if old3 in src:
    src = src.replace(old3, new3, 1); print("[OK] Row 16 → fulfil_total")
else:
    print("[?] Не нашёл строку Озон фулфилмент")

# Строка 17: logistics → fulfil_logistics
old4 = '("    - логистика", "logistics"),'
new4 = '("    - логистика", "fulfil_logistics"),'
if old4 in src:
    src = src.replace(old4, new4, 1); print("[OK] Row 17 → fulfil_logistics")
else:
    print("[?] Не нашёл строку - логистика")

# NEGATIVE
old5 = 'NEGATIVE = {"expenses_total", "expenses_no_ads", "cogs", "commission", "logistics",'
new5 = 'NEGATIVE = {"expenses_total", "expenses_no_ads", "cogs", "commission", "fulfil_total", "fulfil_logistics", "logistics",'
if old5 in src:
    src = src.replace(old5, new5, 1); print("[OK] NEGATIVE дополнен")
else:
    print("[?] NEGATIVE не найден для дополнения")

open("sync_pnl.py", "w", encoding="utf-8").write(src)
print("[OK] sync_pnl.py сохранён")