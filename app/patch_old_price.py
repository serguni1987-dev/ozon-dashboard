src = open("apply_prices.py", encoding="utf-8").read()

# 1. В основном запросе (LIVE) — old_price = new_price
old = '''            {
                "offer_id": u["offer_id"],
                "price": f"{u['target']:.2f}",
                "old_price": f"{u['current']:.2f}",
                "min_price": f"{u['target'] * 0.9:.2f}",
                "currency_code": "RUB",
                "auto_action_enabled": "UNKNOWN",
            }
            for u in updates'''

new = '''            {
                "offer_id": u["offer_id"],
                "price": f"{u['target']:.2f}",
                "old_price": f"{u['target']:.2f}",
                "min_price": f"{u['target'] * 0.9:.2f}",
                "currency_code": "RUB",
                "auto_action_enabled": "UNKNOWN",
            }
            for u in updates'''

if old in src:
    src = src.replace(old, new)
    print("[OK] old_price = target в основном запросе")
else:
    print("[?] Не нашёл блок в основном запросе")

# 2. В rollback — тоже
old_rb = '''    body = {"prices": [{
        "offer_id": offer_id,
        "price": f"{old_price:.2f}",
        "old_price": f"{new_price:.2f}",
        "min_price": f"{old_price * 0.9:.2f}",
        "currency_code": "RUB",
        "auto_action_enabled": "UNKNOWN",
    }]}'''

new_rb = '''    body = {"prices": [{
        "offer_id": offer_id,
        "price": f"{old_price:.2f}",
        "old_price": f"{old_price:.2f}",
        "min_price": f"{old_price * 0.9:.2f}",
        "currency_code": "RUB",
        "auto_action_enabled": "UNKNOWN",
    }]}'''

if old_rb in src:
    src = src.replace(old_rb, new_rb)
    print("[OK] old_price = old_price в rollback")
else:
    print("[?] Не нашёл блок rollback")

open("apply_prices.py", "w", encoding="utf-8").write(src)
print("\nГотово.")
