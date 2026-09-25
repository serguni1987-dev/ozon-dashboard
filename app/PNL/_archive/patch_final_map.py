"""
patch_final_map.py — финальный CATEGORY_MAP, всё сходится с эталоном.
"""
src = open("calc_monthly_summary.py", encoding="utf-8").read()

old = '''CATEGORY_MAP = {
    32: "Логистика", 59: "Логистика", 98: "Логистика",
    1: "Услуги агентов", 74: "Услуги агентов", 79: "Услуги агентов", 3: "Услуги агентов",
    71: "Услуги FBO", 46: "Услуги FBO",
    93: "Другие услуги",
    18: "Прочие", 20: "Прочие",
    # Остальные - без категории, чтобы видеть, что не классифицировано
}'''

new = '''CATEGORY_MAP = {
    # Логистика
    32: "Логистика",   # Logistic
    59: "Логистика",   # ReturnFlowLogistic
    98: "Логистика",   # DeliveryToHandoverPlaceByOzon

    # Услуги агентов (по эталону = 9 028,22)
    1: "Услуги агентов",   # Acquiring
    74: "Услуги агентов",  # StarsMembership
    79: "Услуги агентов",  # TemporaryPlacementsAgent
    29: "Услуги агентов",  # LastMileCourier
    76: "Услуги агентов",  # StockInsurance
    45: "Услуги агентов",  # PickUpPointReturnAcceptance

    # Реклама и ДРР
    3: "Реклама",      # BrandCommission

    # Услуги FBO
    71: "Услуги FBO",  # SellerReturns
    46: "Услуги FBO",  # Placements

    # Другие услуги
    93: "Другие услуги",  # DefectFineErrors

    # Прочие начисления
    18: "Прочие",      # EarlyPayment
    20: "Прочие",      # FlexiblePayments
}'''

if old in src:
    src = src.replace(old, new)
    open("calc_monthly_summary.py", "w", encoding="utf-8").write(src)
    print("[OK] CATEGORY_MAP обновлён — финальный")
else:
    print("[?] Не нашёл CATEGORY_MAP. Ищу фрагмент:")
    idx = src.find("CATEGORY_MAP")
    print(src[idx:idx+600])
