"""Показывает ИМЕНА ключей в .env (без значений) + подсказки."""
from pathlib import Path

PROJECT = Path(r"C:\Users\sergu\Desktop\проект")
APP     = PROJECT / "app"

found = {}
for p in (PROJECT / ".env", APP / ".env"):
    print(f"--- {p} ---")
    if not p.exists():
        print("  (нет файла)")
        continue
    text = p.read_text(encoding="utf-8", errors="replace")
    for i, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, _, v = s.partition("=")
        k = k.strip()
        v_clean = v.strip().strip('"').strip("'")
        found[k] = v_clean
        print(f"  {i:>3}  {k:<30} len={len(v_clean)}")

print()
print("=== Подбор Client-Id ===")
for cand in ("OZON_CLIENT_ID", "OZON_CLIENT", "CLIENT_ID",
             "OZON_SELLER_CLIENT_ID", "SELLER_CLIENT_ID", "OZON_ID"):
    if cand in found:
        print(f"  НАЙДЕНО: {cand} (len={len(found[cand])})")

print()
print("=== Все ключи с именем, содержащим 'CLIENT' ===")
for k in found:
    if "CLIENT" in k.upper():
        print(f"  {k} (len={len(found[k])})")

print()
print("=== Все ключи с именем, содержащим 'OZON' ===")
for k in found:
    if "OZON" in k.upper():
        print(f"  {k} (len={len(found[k])})")
