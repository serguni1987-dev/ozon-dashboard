"""check_costs_alert.py - tri proverki:
1. SKU iz realizacii bez cost_price / is_own=1
2. Novye type_id (uslugi Ozon vne CATEGORY_MAP)
3. SKU iz sales_daily bez cost_price (svezhee)
"""
import sqlite3, sys, os

# sys.path для импорта sync_pnl
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "PNL"))

c = sqlite3.connect("ozon.db")
c.row_factory = sqlite3.Row
problems = []

# ── 1. SKU iz monthly_realization_rows bez cost_price ──
for r in c.execute("""
    SELECT DISTINCT mr.sku, mr.offer_id
    FROM monthly_realization_rows mr
    LEFT JOIN products p ON p.sku = mr.sku
    WHERE p.cost_price IS NULL OR p.cost_price = 0
"""):
    problems.append(f"  [COST]   realizaciya bez cost: sku={r['sku']} offer_id={r['offer_id']}")

# ── 1b. SKU iz monthly_realization_rows bez is_own=1 ──
for r in c.execute("""
    SELECT DISTINCT mr.sku, mr.offer_id
    FROM monthly_realization_rows mr
    LEFT JOIN products p ON p.sku = mr.sku
    WHERE p.is_own IS NULL OR p.is_own = 0
"""):
    problems.append(f"  [IS_OWN] realizaciya bez is_own=1: sku={r['sku']} offer_id={r['offer_id']}")

# ── 2. Novye type_id (B) ──
try:
    import sync_pnl
    known_ids = set(sync_pnl.CATEGORY_MAP.keys())
except Exception as e:
    known_ids = set()
    print(f"[!] Ne smog zagruzit' CATEGORY_MAP: {e}")

if known_ids:
    placeholders = ",".join("?" * len(known_ids))
    unknown = c.execute(f"""
        SELECT type_id, type_name, COUNT(*) AS n, SUM(ABS(amount)) AS total
        FROM accruals_services
        WHERE date >= '2026-09-01'
          AND type_id NOT IN ({placeholders})
        GROUP BY type_id, type_name
        ORDER BY total DESC
    """, tuple(known_ids)).fetchall()

    for u in unknown:
        problems.append(
            f"  [TYPE]   novyj type_id={u['type_id']} {u['type_name']!r} "
            f"n={u['n']} summa={u['total']:,.2f}"
        )

# ── 3. SKU iz sales_daily bez cost_price (D) ──
for r in c.execute("""
    SELECT DISTINCT sd.sku, p.offer_id, SUM(sd.delivered) AS dlv
    FROM sales_daily sd
    LEFT JOIN products p ON p.sku = sd.sku
    WHERE sd.date >= '2026-09-01'
      AND sd.delivered > 0
      AND (p.cost_price IS NULL OR p.cost_price = 0)
    GROUP BY sd.sku
    ORDER BY dlv DESC
"""):
    problems.append(
        f"  [SALES]  sales_daily bez cost: sku={r['sku']} offer_id={r['offer_id']} "
        f"delivered={r['dlv']}"
    )

c.close()

if problems:
    print("=" * 70)
    print("[!] ALERT: problemy s sebestoimostyu / klassifikaciej")
    print("=" * 70)
    for p in problems[:40]:
        print(p)
    if len(problems) > 40:
        print(f"  ... i eshe {len(problems) - 40}")
    print()
    print("Dejstviya:")
    print("  [COST] / [SALES] -> dobav' v costs_all.csv i zapusti import_costs.py")
    print("  [IS_OWN]         -> zapusti mark_brands.py")
    print("  [TYPE]           -> dobav' v CATEGORY_MAP v PNL/sync_pnl.py")
    sys.exit(1)
else:
    print("[OK] Sebestoimost' i klassifikaciya v poryadke")
    sys.exit(0)
