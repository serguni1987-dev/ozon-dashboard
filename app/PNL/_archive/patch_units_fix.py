"""patch_units_fix.py — if units > 0 → if units != 0 (учитывать возвраты)."""

src = open("PNL/sync_pnl.py", encoding="utf-8").read()
OLD = """        units = int(r[0] or 0) if r else 0
        if units > 0:
            cogs += cost * units"""
NEW = """        units = int(r[0] or 0) if r else 0
        if units != 0:
            cogs += cost * units"""

if OLD in src:
    src = src.replace(OLD, NEW, 1)
    open("PNL/sync_pnl.py", "w", encoding="utf-8").write(src)
    print("[OK] units != 0 — возвраты учитываются")
else:
    print("[?] Не нашёл блок")