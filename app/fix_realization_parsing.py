src = open("sync_monthly.py", encoding="utf-8").read()

# Заменяем блок парсинга
old = '''        sku = item.get("sku")
        offer_id = item.get("offer_id")
        barcode = item.get("barcode")
        item_name = item.get("name")
        seller_price = to_float(row.get("seller_price_per_instance"))
        quantity = int(dc.get("quantity") or 0)
        commission_ratio = row.get("commission_ratio") or 0

        # delivery_commission
        dc_amount = to_float(dc.get("amount"))
        dc_bonus = to_float(dc.get("bonus"))
        dc_comm = to_float(dc.get("commission"))
        dc_comp = to_float(dc.get("compensation"))
        dc_total = to_float(dc.get("total"))

        # return_commission
        rc_amount = to_float(rc.get("amount"))
        rc_bonus = to_float(rc.get("bonus"))
        rc_comm = to_float(rc.get("commission"))
        rc_comp = to_float(rc.get("compensation"))
        rc_total = to_float(rc.get("total"))

        # Звёзды
        stars = to_float(dc.get("stars")) + to_float(rc.get("stars"))

        # Накапливаем
        seller_price_sum += seller_price * quantity
        commission_sum += dc_comm + rc_comm
        bonus_sum += dc_bonus + rc_bonus
        compensation_sum += dc_comp + rc_comp
        delivery_sum += dc_amount + rc_amount
        return_commission_sum += rc_comm
        stars_sum += stars'''

new = '''        sku = item.get("sku")
        offer_id = item.get("offer_id")
        barcode = item.get("barcode")
        item_name = item.get("name")
        seller_price = to_float(row.get("seller_price_per_instance"))
        quantity = int(dc.get("quantity") or 0)
        commission_ratio = row.get("commission_ratio") or 0

        # === delivery_commission ===
        dc_amount = to_float(dc.get("amount"))          # что заплатил покупатель
        dc_price = to_float(dc.get("price_per_instance"))  # цена покупателя
        dc_bonus = to_float(dc.get("bonus"))            # баллы за скидку
        dc_comm = to_float(dc.get("commission"))        # доп. комиссия (обычно 0)
        dc_comp = to_float(dc.get("compensation"))      # компенсации
        dc_std_fee = to_float(dc.get("standard_fee"))   # гросс-комиссия Ozon
        dc_total = to_float(dc.get("total"))            # итого удержано
        dc_bank_ci = to_float(dc.get("bank_coinvestment"))
        dc_pickup_ci = to_float(dc.get("pick_up_point_coinvestment"))
        dc_stars = to_float(dc.get("stars"))

        # === return_commission ===
        rc_amount = to_float(rc.get("amount"))
        rc_bonus = to_float(rc.get("bonus"))
        rc_comm = to_float(rc.get("commission"))
        rc_comp = to_float(rc.get("compensation"))
        rc_std_fee = to_float(rc.get("standard_fee"))
        rc_total = to_float(rc.get("total"))
        rc_bank_ci = to_float(rc.get("bank_coinvestment"))
        rc_pickup_ci = to_float(rc.get("pick_up_point_coinvestment"))
        rc_stars = to_float(rc.get("stars"))

        # Логистика = total − standard_fee (что удержано сверх комиссии)
        logistics_dc = dc_total - dc_std_fee
        logistics_rc = rc_total - rc_std_fee

        # Эффективная комиссия = total − bonus − coinvestment
        coinv_dc = dc_bank_ci + dc_pickup_ci
        coinv_rc = rc_bank_ci + rc_pickup_ci
        effective_fee_dc = dc_total - dc_bonus - coinv_dc
        effective_fee_rc = rc_total - rc_bonus - coinv_rc

        # Накапливаем (с учётом направления возвратов)
        # В возвратах total и standard_fee могут быть отрицательными
        seller_price_sum += seller_price * quantity
        sale_price_sum += dc_amount + rc_amount
        gross_commission_sum += dc_std_fee + rc_std_fee
        bonus_sum += dc_bonus + rc_bonus
        coinvestment_sum += coinv_dc + coinv_rc
        logistics_sum += logistics_dc + logistics_rc
        total_held_sum += dc_total + rc_total
        effective_fee_sum += effective_fee_dc + effective_fee_rc
        stars_sum += dc_stars + rc_stars'''

if old in src:
    src = src.replace(old, new)
    print("[OK] Блок парсинга переписан")
else:
    print("[?] Не нашёл блок парсинга")

# Добавляем счётчики
old2 = '''    seller_price_sum = 0.0
    commission_sum = 0.0
    bonus_sum = 0.0
    compensation_sum = 0.0
    delivery_sum = 0.0
    return_commission_sum = 0.0
    stars_sum = 0.0'''

new2 = '''    seller_price_sum = 0.0
    sale_price_sum = 0.0
    gross_commission_sum = 0.0
    bonus_sum = 0.0
    coinvestment_sum = 0.0
    logistics_sum = 0.0
    total_held_sum = 0.0
    effective_fee_sum = 0.0
    stars_sum = 0.0'''

if old2 in src:
    src = src.replace(old2, new2)
    print("[OK] Счётчики обновлены")

# Меняем вывод
old3 = '''    print(f"\\n[2] СУММЫ ИЗ ОТЧЁТА:")
    print(f"    Реализовано (цена продавца):  {seller_price_sum:>14,.2f} ?")
    print(f"    Комиссия Ozon:                {commission_sum:>14,.2f} ?")
    print(f"    Баллы за скидки:              {bonus_sum:>14,.2f} ?")
    print(f"    Компенсации Ozon:             {compensation_sum:>14,.2f} ?")
    print(f"    Логистика:                    {delivery_sum:>14,.2f} ?")
    print(f"    Звёзды:                       {stars_sum:>14,.2f} ?")

    # Налоговая база = выручка от реализации ? баллы за скидки
    # (по отчёту реализации: доход = продажи ? возвраты, баллы вычитаются)
    tax_base = seller_price_sum - abs(bonus_sum)
    tax_15 = tax_base * TAX_RATE

    # Чистая прибыль = выручка ? комиссия ? логистика ? баллы ? налог
    # (баллы уже компенсированы, но налоговая база их не учитывает)
    gross = seller_price_sum + bonus_sum  # фактически получено
    net = gross - abs(commission_sum) - abs(delivery_sum) - tax_15

    print(f"\\n[3] РАСЧЁТ НАЛОГА И ПРИБЫЛИ:")
    print(f"    Налоговая база:               {tax_base:>14,.2f} ?")
    print(f"    Налог УСН 15%:                {tax_15:>14,.2f} ?")
    print(f"    Чистая прибыль (оценка):      {net:>14,.2f} ?")'''

new3 = '''    print(f"\\n[2] СУММЫ ИЗ ОТЧЁТА:")
    print(f"    Seller price (ваша цена):      {seller_price_sum:>14,.2f} ₽")
    print(f"    Sale price (покупатель):       {sale_price_sum:>14,.2f} ₽")
    print(f"    Разница (скидка Ozon):         {seller_price_sum - sale_price_sum:>14,.2f} ₽")
    print(f"    ")
    print(f"    Гросс-комиссия Ozon:           {gross_commission_sum:>14,.2f} ₽")
    print(f"    Баллы за скидки:               {bonus_sum:>14,.2f} ₽")
    print(f"    Соинвестирование:              {coinvestment_sum:>14,.2f} ₽")
    print(f"    Логистика:                     {logistics_sum:>14,.2f} ₽")
    print(f"    ")
    print(f"    Итого удержано (total):        {total_held_sum:>14,.2f} ₽")
    print(f"    ЭФФЕКТИВНАЯ КОМИССИЯ:          {effective_fee_sum:>14,.2f} ₽")
    if seller_price_sum:
        print(f"    % от seller_price:             {effective_fee_sum/seller_price_sum*100:>14,.2f}%")

    # Проверка: bonus + coinv должно быть ≈ (seller_price − sale_price)
    print(f"\\n    ПРОВЕРКА:")
    print(f"    bonus + coinv:                 {bonus_sum + coinvestment_sum:>14,.2f} ₽")
    print(f"    seller − sale:                 {seller_price_sum - sale_price_sum:>14,.2f} ₽")

    # Налоговая база = sale_price − bonus (по логике приложения)
    tax_base = sale_price_sum - bonus_sum
    tax_15 = tax_base * TAX_RATE

    # Чистая прибыль продавца
    # = seller_price − effective_fee_sum
    # (эффективная комиссия уже учитывает и комиссию, и логистику, и компенсации)
    net = seller_price_sum - effective_fee_sum - tax_15

    print(f"\\n[3] РАСЧЁТ НАЛОГА И ПРИБЫЛИ:")
    print(f"    Налоговая база:                {tax_base:>14,.2f} ₽")
    print(f"    Налог УСН 15%:                 {tax_15:>14,.2f} ₽")
    print(f"    Чистая прибыль:                {net:>14,.2f} ₽")'''

if old3 in src:
    src = src.replace(old3, new3)
    print("[OK] Вывод переписан")

# Обновляем INSERT
old4 = '''        seller_price_sum, commission_sum, bonus_sum, compensation_sum,
        delivery_sum, return_commission_sum, stars_sum,
        commission_sum + bonus_sum + compensation_sum,'''
new4 = '''        seller_price_sum, gross_commission_sum, bonus_sum, coinvestment_sum,
        logistics_sum, 0, stars_sum,
        total_held_sum,'''
if old4 in src:
    src = src.replace(old4, new4)
    print("[OK] INSERT обновлён")

open("sync_monthly.py", "w", encoding="utf-8").write(src)
print()
print("Готово. Запускай: py sync_monthly.py")
