src = open("sheets_sync.py", encoding="utf-8").read()

# Старый блок рекомендаций
old = """        # Рекомендация менеджеру
        if color == "RED" and min_p > 0:
            target = min_p * 1.02
            new_profit = target * (1 - COMMISSION_PCT - SERVICES_PCT) - cost
            if new_profit > 0:
                recommend = f"↓ Снизить до {target:,.0f} ₽"
            else:
                recommend = "→ Снять (маржа уйдёт в минус)"
        elif color == "SUPER" and min_p > price * 0.95:
            new_target = price * 1.10
            recommend = f"↑ Поднять до {new_target:,.0f} ₽"
        elif color == "GREEN" and min_p > 0 and price < min_p * 0.9:
            new_target = price * 1.05
            recommend = f"↑ Поднять до {new_target:,.0f} ₽"
        elif unit_profit < 0:
            recommend = "❌ Убыток — поднять цену"
        elif orders == 0:
            recommend = "○ Наблюдать"
        else:
            recommend = "✓ Оставить"
"""

# Новый блок
new = """        # Рекомендация менеджеру
        if unit_profit < 0:
            recommend = "❌ Убыток — срочно поднять"
        elif color == "RED" and min_p > 0:
            target = min_p * 1.02
            new_profit = target * (1 - COMMISSION_PCT - SERVICES_PCT) - cost
            if new_profit > 0:
                recommend = f"↓ Снизить до {target:,.0f} ₽"
            else:
                recommend = "→ Снять (маржа уйдёт в минус)"
        elif color == "SUPER" and orders > 0:
            # SUPER + продаётся = можно смело поднять 7-15%
            step = price * 1.07
            if min_p > price * 1.05:
                step = min(min_p * 1.02, price * 1.15)
            target = step
            pct = (target / price - 1) * 100
            recommend = f"↑ Поднять до {target:,.0f} ₽ (+{pct:.0f}%)"
        elif color == "SUPER" and orders == 0:
            recommend = "🔍 SUPER, но не продаётся — проверить карточку"
        elif color == "GREEN" and orders > 0:
            step = price * 1.05
            if min_p > price * 1.05:
                step = min(min_p * 1.02, price * 1.10)
            target = step
            pct = (target / price - 1) * 100
            recommend = f"↑ Поднять до {target:,.0f} ₽ (+{pct:.0f}%)"
        elif orders == 0:
            recommend = "○ Наблюдать"
        else:
            recommend = "✓ Оставить"
"""

if old in src:
    src = src.replace(old, new)
    open("sheets_sync.py", "w", encoding="utf-8").write(src)
    print("[OK] Рекомендации обновлены")
else:
    print("[?] Не нашёл блок рекомендаций. Показываю фрагмент для диагностики:")
    idx = src.find("# Рекомендация менеджеру")
    if idx > 0:
        print(src[idx:idx+800])
