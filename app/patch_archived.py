"""patch_archived.py — добавляет AND is_archived = 0 в ключевые скрипты."""
import re

FILES = ["cleanup_dead.py", "hot_carts.py", "worklist.py", "daily_dashboard.py"]

for fname in FILES:
    try:
        with open(fname, encoding="utf-8") as f:
            src = f.read()
    except FileNotFoundError:
        print(f"[SKIP] {fname}")
        continue

    if "is_archived" in src:
        print(f"[i] {fname} — уже есть фильтр")
        continue

    new, n = re.subn(r"(p\.is_own\s*=\s*1)", r"\1 AND p.is_archived = 0", src)
    if n == 0:
        new, n = re.subn(r"(is_own\s*=\s*1)", r"\1 AND is_archived = 0", src)

    if n > 0:
        with open(fname, "w", encoding="utf-8") as f:
            f.write(new)
        print(f"[OK] {fname} — добавлено фильтров: {n}")
    else:
        print(f"[?] {fname} — не найдено 'is_own = 1'")
