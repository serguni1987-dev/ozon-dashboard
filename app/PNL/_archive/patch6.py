"""patch6: abs() к категориям при суммировании расходов."""
import shutil
from datetime import datetime

SRC = "PNL/sync_pnl.py"
bak = f"{SRC}.bak6-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
shutil.copy(SRC, bak)
print(f"Бэкап: {bak}")

src = open(SRC, encoding="utf-8").read()

old = '''    ads = cats.get("Реклама PPC", 0)
    services_no_ads = sum(v for k, v in cats.items()
                       if k not in ("Реклама", "ItemCompensation"))
    expenses_no_ads = commission + services_no_ads - cats.get("ItemCompensation", 0)'''

new = '''    ads = abs(cats.get("Реклама PPC", 0))
    services_no_ads = sum(abs(v) for k, v in cats.items()
                       if k not in ("Реклама PPC", "ItemCompensation"))
    expenses_no_ads = commission + services_no_ads - abs(cats.get("ItemCompensation", 0))'''

if old in src:
    src = src.replace(old, new)
    print("[OK] expenses_no_ads теперь abs(services_no_ads)")
else:
    print("[?] НЕ найден блок ads/services_no_ads")
    # Показать что там сейчас
    import re
    m = re.search(r'    ads = .*?\n    services_no_ads.*?\n    expenses_no_ads.*?\n', src)
    if m:
        print("Сейчас в файле:")
        print(m.group(0))

open(SRC, "w", encoding="utf-8").write(src)
