"""
patch_dashboard_actions.py — заменяет block_actions в daily_dashboard.py
на версию, использующую plan_core.get_actions().
"""
import re

src = open("daily_dashboard.py", encoding="utf-8").read()

# Находим и заменяем функцию block_actions целиком
pattern = re.compile(
    r"def block_actions\(con\):.*?(?=\ndef block_money)",
    re.DOTALL
)

new_func = '''def block_actions(con):
    line()
    print("ДЕЛАЙ")
    line()

    from plan_core import get_actions

    max_date = con.execute("SELECT MAX(date) FROM sales_daily").fetchone()[0]
    month_ago = (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")

    actions = get_actions(con, month_ago, max_date)

    if not actions:
        print("\\n  Действий нет.")
        print()
        return

    total_effect = sum(a["effect"] for a in actions)

    # Группируем по категориям для краткой сводки
    cats = {}
    for a in actions:
        cats.setdefault(a["category"], []).append(a)

    print(f"\\n  Всего SKU к работе: {len(actions)}, "
          f"потенциал: {total_effect:,.0f} ₽/мес")
    print(f"  {'Категория':<12} {'SKU':>4} {'Эффект':>12}")
    print("  " + "-" * 32)
    for cat in ["УБЫТОЧНЫЙ", "ДОСТАВКА", "КАРТОЧКА", "КРИТ. МАРЖА", "МАСШТАБ"]:
        if cat in cats:
            grp = cats[cat]
            grp_effect = sum(g["effect"] for g in grp)
            print(f"  {cat:<12} {len(grp):>4} {grp_effect:>11,.0f} ₽")

    # Топ-10 действий
    print(f"\\n  ТОП-10 действий:")
    print(f"  {'#':<4} {'Категория':<12} {'Offer ID':<18} {'Что':<32} {'Эффект':>10}")
    print("  " + "-" * 84)
    for i, a in enumerate(actions[:10], 1):
        name = (a["name"] or "")[:31]
        print(f"  {i:<4} {a['category']:<12} {a['offer_id']:<18} {name:<32} "
              f"{a['effect']:>9,.0f} ₽")
    print()


'''

new_src, n = pattern.subn(new_func, src)

if n == 0:
    print("[FAIL] Не удалось найти block_actions")
else:
    open("daily_dashboard.py", "w", encoding="utf-8").write(new_src)
    print(f"[OK] block_actions заменён. Запускай: py daily_dashboard.py")
