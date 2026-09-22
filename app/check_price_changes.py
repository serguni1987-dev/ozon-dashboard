import sqlite3
con = sqlite3.connect("ozon.db")
con.row_factory = sqlite3.Row

print("=== price_changes ===")
for r in con.execute("""
    SELECT id, changed_at, offer_id, old_price, new_price, api_status,
           rolled_back, rollback_at, batch_id
    FROM price_changes ORDER BY id DESC
"""):
    rolled = " [ОТКАЧЕНО]" if r["rolled_back"] else ""
    print(f"  id={r['id']}  {r['changed_at']}  {r['offer_id']:<18} "
          f"{r['old_price']:>7,.0f} → {r['new_price']:>7,.0f}  "
          f"{r['api_status']:<6}{rolled}  batch={r['batch_id']}")

print(f"\nВсего записей: {con.execute('SELECT COUNT(*) FROM price_changes').fetchone()[0]}")
print(f"Откачено: {con.execute('SELECT COUNT(*) FROM price_changes WHERE rolled_back = 1').fetchone()[0]}")
con.close()
