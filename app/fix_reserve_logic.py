"""
fix_reserve_logic.py — убирает двойной счёт резерва закупок.
Резерв закупок = план из procurement_plan (или 0, если плана нет).
Резерв штрафов = 3% (не 5%).
"""
src = open("calc_capital.py", encoding="utf-8").read()

old = '''    # === 2. ЧТО ЗАБРАТЬ ===
    print("\\n[2] ЧТО ЗАБРАТЬ")

    # Резервы
    reserve_tax = tax_reserve
    reserve_proc = revenue_30 * RESERVE_PROCUREMENT
    reserve_fines = revenue_30 * RESERVE_FINES

    # Свободно = на счету + у Ozon − резервы
    free_money = on_account + owed_by_ozon - reserve_tax - reserve_proc - reserve_fines

    print(f"  На счету + у Ozon:      {money(on_account + owed_by_ozon)}")
    print(f"  − Резерв налога:        {money(-reserve_tax)}")
    print(f"  − Резерв закупок (10%): {money(-reserve_proc)}")
    print(f"  − Резерв штрафов (5%):  {money(-reserve_fines)}")
    print(f"  ─────────────────────────────────")
    print(f"  МОЖНО ЗАБРАТЬ:          {money(max(0, free_money))}")

    if free_money > 0:
        print(f"  ✅ Свободные деньги есть")
    else:
        print(f"  ⚠️ Свободных денег нет — всё в резервах")'''

new = '''    # === 2. ЧТО ЗАБРАТЬ ===
    print("\\n[2] ЧТО ЗАБРАТЬ")

    # Резервы
    reserve_tax = tax_reserve

    # Резерв закупок = план из procurement_plan (только будущие платежи)
    today = datetime.now()
    plan_proc = con.execute("""
        SELECT SUM(amount) FROM procurement_plan
        WHERE status = 'planned' AND due_date >= ?
    """, (today.strftime("%Y-%m-%d"),)).fetchone()[0] or 0

    # Резерв штрафов = 3% от выручки
    reserve_fines = revenue_30 * 0.03

    # Свободно = на счету + у Ozon − налог − план закупок − штрафы
    free_money = on_account + owed_by_ozon - reserve_tax - plan_proc - reserve_fines

    print(f"  На счету + у Ozon:      {money(on_account + owed_by_ozon)}")
    print(f"  − Резерв налога:        {money(-reserve_tax)}")
    if plan_proc > 0:
        print(f"  − План закупок:         {money(-plan_proc)}")
    else:
        print(f"  − План закупок:         0 ₽  (нет плана)")
    print(f"  − Резерв штрафов (3%):  {money(-reserve_fines)}")
    print(f"  ─────────────────────────────────")
    print(f"  МОЖНО ЗАБРАТЬ:          {money(max(0, free_money))}")

    if free_money > 50000:
        print(f"  ✅ Свободно {free_money:,.0f} ₽ — можно забрать")
    elif free_money > 10000:
        print(f"  ⚠️ Свободно {free_money:,.0f} ₽ — забирать осторожно")
    else:
        print(f"  ❌ Свободных денег мало ({free_money:,.0f} ₽)")

    # Пояснение
    print(f"\\n  ПОЯСНЕНИЕ:")
    print(f"    На счету: {money(on_account)}")
    print(f"    У Ozon:   {money(owed_by_ozon)}  (точно из API)")
    print(f"    В товаре: {money(frozen)}  (уже закуплено, не резерв)")
    print(f"    Налог:    {money(reserve_tax)}  (реальный отложенный расход)")'''

if old in src:
    src = src.replace(old, new)
    print("[OK] Логика резервов исправлена")
else:
    print("[?] Не нашёл блок ЧТО ЗАБРАТЬ")

open("calc_capital.py", "w", encoding="utf-8").write(src)
print("Готово. Запускай: py calc_capital.py")
