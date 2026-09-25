src = open("sync_monthly.py", encoding="utf-8").read()

# 1. Добавить извлечение rc_amount
old1 = '''        # return_commission
        rc_bonus = to_float(rc.get("bonus"))'''
new1 = '''        # return_commission
        rc_amount = to_float(rc.get("amount"))
        rc_bonus = to_float(rc.get("bonus"))'''
if old1 in src:
    src = src.replace(old1, new1)
    print("[OK] rc_amount добавлен")
else:
    print("[?] Не нашёл блок return_commission")

# 2. Исправить формулы (delivery − return)
old2 = '''        # Итого по строке
        total_seller_price = seller_price * dc_qty
        total_sale_price = dc_amount
        total_bonus = dc_bonus + rc_bonus
        total_coinv = dc_bank_ci + dc_pickup_ci + rc_bank_ci + rc_pickup_ci
        total_gross_fee = dc_std_fee + rc_std_fee
        total_held = dc_total + rc_total
        total_logistics = total_held - total_gross_fee
        total_eff = total_held - total_bonus - total_coinv
        total_stars = dc_stars + rc_stars'''

new2 = '''        # Итого по строке — delivery МИНУС return
        total_seller_price = seller_price * dc_qty
        total_sale_price = dc_amount - rc_amount
        total_bonus = dc_bonus - rc_bonus
        total_coinv = (dc_bank_ci + dc_pickup_ci) - (rc_bank_ci + rc_pickup_ci)
        total_gross_fee = dc_std_fee - rc_std_fee
        total_held = dc_total - rc_total
        total_logistics = total_held - total_gross_fee
        total_eff = total_held - total_bonus - total_coinv
        total_stars = dc_stars - rc_stars'''

if old2 in src:
    src = src.replace(old2, new2)
    print("[OK] Формулы исправлены: delivery − return")
else:
    print("[?] Не нашёл блок 'Итого по строке'")

# 3. Добавить 76 и 45 обратно в классификацию (чтобы 'Без категории' стал 0)
# Но по-другому: 76 и 45 — это minor услуги, оставим без категории? Нет, вернём.

open("sync_monthly.py", "w", encoding="utf-8").write(src)
print("\nГотово.")
