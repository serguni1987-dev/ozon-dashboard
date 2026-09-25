import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sync_pnl import get_pnl_for_month

data = get_pnl_for_month("2026-08")

print("=" * 70)
print("P&L АВГУСТ — контрольная сверка с эталоном")
print("=" * 70)
print()
print(f"{'Метрика':<25} {'Наше':>14} {'Эталон':>14} {'Δ':>12}")
print("-" * 68)

etalon = {
    "revenue": 302967.00,
    "sale_price": 161382.96,
    "bonus": 139902.77,
    "coinv": 1681.27,
    "commission": 151050.09,
    "cogs": 111319.00,
    "margin": 15629.34,
}

for key, label in [
    ("revenue", "Выручка"),
    ("sale_price", "От реализации"),
    ("bonus", "Баллы"),
    ("coinv", "Партнёры"),
    ("commission", "Комиссия"),
    ("cogs", "Себестоимость"),
    ("margin", "Валовая"),
]:
    our = data.get(key, 0)
    et = etalon.get(key, 0)
    delta = our - et
    mark = "OK" if abs(delta) < 1 else ("~" if abs(delta) < 2000 else "X")
    print(f"{label:<25} {our:>14,.2f} {et:>14,.2f} {delta:>+12,.2f} {mark}")
