"""Патч sync_pnl.py: COGS из realization + фикс ads."""
import os, shutil
from datetime import datetime

SRC = "PNL/sync_pnl.py"
if not os.path.exists(SRC):
    print(f"Не найден {SRC}")
    raise SystemExit(1)

bak = f"{SRC}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
shutil.copy(SRC, bak)
print(f"Бэкап: {bak}")

src = open(SRC, encoding="utf-8").read()

start_marker = "    # Себестоимость: delivered"
end_marker = "    con.close()"

i = src.find(start_marker)
if i == -1:
    print("НЕ нашёл start_marker")
    raise SystemExit(2)

j = src.find(end_marker, i)
if j == -1:
    print("НЕ нашёл end_marker")
    raise SystemExit(3)

print(f"start найден на позиции {i}")
print(f"end найден на позиции {j}")
print()
print("--- СТАРЫЙ БЛОК (первые 400 символов) ---")
print(src[i:i+400])
print("--- /СТАРЫЙ БЛОК ---")

new_block = (
    "    # Себестоимость = продажи × cost.\n"
    "    # Источник: monthly_realization_rows (то, что Ozon кладёт в Отчёт по экономике).\n"
    "    # Возвраты (is_return=1) не учитываем.\n"
    "    cogs = 0.0\n"
    "    for r in con.execute(\"\"\"\n"
    "        SELECT sku, SUM(quantity) AS q\n"
    "        FROM monthly_realization_rows\n"
    "        WHERE month = ? AND is_return = 0 AND quantity > 0\n"
    "        GROUP BY sku\n"
    "    \"\"\", (month,)):\n"
    "        sku = r[\"sku\"]\n"
    "        qty = f(r[\"q\"])\n"
    "        if qty <= 0:\n"
    "            continue\n"
    "\n"
    "        r2 = con.execute(\"\"\"\n"
    "            SELECT cost_price FROM product_cost_history\n"
    "            WHERE sku = ? AND date_from < ?\n"
    "            ORDER BY date_from DESC LIMIT 1\n"
    "        \"\"\", (sku, d2)).fetchone()\n"
    "        cost = f(r2[0]) if r2 and r2[0] else 0\n"
    "        if cost == 0:\n"
    "            continue\n"
    "\n"
    "        cogs += cost * qty\n"
    "\n"
)

src2 = src[:i] + new_block + src[j:]
src2 = src2.replace('ads = cats.get("Реклама", 0)', 'ads = cats.get("Реклама PPC", 0)')

open(SRC, "w", encoding="utf-8").write(src2)
print()
print("[OK] Файл обновлён")
print(f"  monthly_realization_rows в новом блоке: {'monthly_realization_rows' in src2}")
print(f"  старый sales_daily fallback удалён: {'fallback accruals.POSTING' not in src2}")
print(f"  ads использует Реклама PPC: {'Реклама PPC' in src2}")
