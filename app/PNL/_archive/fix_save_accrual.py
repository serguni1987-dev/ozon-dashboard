"""
fix_save_accrual.py — перезаписывает save_accrual целиком.
"""
import re

src = open("sync_finance.py", encoding="utf-8").read()

# Ищем функцию save_accrual целиком (до def main)
pattern = re.compile(
    r"def save_accrual\(cur, acc, types\):.*?(?=\ndef main\()",
    re.DOTALL
)

new_func = '''def save_accrual(cur, acc, types):
    accrual_id = acc.get("accrual_id")
    date_str = acc.get("date")
    if not accrual_id or not date_str:
        return 0, 0

    posting = acc.get("posting") or {}
    products = posting.get("products") or []
    schema = posting.get("delivery_schema")
    unit = acc.get("unit_number")
    category = acc.get("accrued_category")
    total = to_float(acc.get("total_amount"))

    raw_json_str = json.dumps(acc, ensure_ascii=False)

    n_acc = 0
    n_svc = 0

    # Если products пустой — сохраняем запись с sku=None
    if not products:
        cur.execute("""
            INSERT OR REPLACE INTO accruals
            (accrual_id, date, sku, unit_number, accrued_category, delivery_schema,
             seller_price, sale_price, sale_commission, bonus, coinvestment, total_amount,
             raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (accrual_id, date_str, None, unit, category, schema,
              None, None, None, None, None, total, raw_json_str))
        n_acc += 1

        # Услуги могут быть на верхнем уровне (без products)
        for block_name in ("item_fees", "non_item_fee", "container_fees"):
            block = acc.get(block_name)
            if not block:
                continue
            items = block if isinstance(block, list) else [block]
            for it in items:
                tid = it.get("type_id")
                amt = to_float(it.get("accrued")) or to_float(it)
                if tid is None or amt is None:
                    continue
                cur.execute("""
                    INSERT INTO accruals_services
                    (accrual_id, date, sku, type_id, type_name, amount)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (accrual_id, date_str, None, tid,
                      types.get(tid, f"type_{tid}"), amt))
                n_svc += 1
        return n_acc, n_svc

    # Есть products — обходим каждый
    for p in products:
        sku = p.get("sku")
        comm = p.get("commission") or {}
        sp = to_float(comm.get("seller_price"))
        slp = to_float(comm.get("sale_price"))
        cm = to_float(comm.get("sale_commission") or comm.get("commission"))
        bn = to_float(comm.get("bonus"))
        ci = to_float(comm.get("coinvestment"))

        cur.execute("""
            INSERT OR REPLACE INTO accruals
            (accrual_id, date, sku, unit_number, accrued_category, delivery_schema,
             seller_price, sale_price, sale_commission, bonus, coinvestment, total_amount,
             raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (accrual_id, date_str, sku, unit, category, schema,
              sp, slp, cm, bn, ci, total, raw_json_str))
        n_acc += 1

        # Services внутри delivery
        delivery = p.get("delivery") or {}
        for svc in delivery.get("services") or []:
            tid = svc.get("type_id")
            amt = to_float(svc.get("accrued"))
            if tid is None or amt is None:
                continue
            cur.execute("""
                INSERT INTO accruals_services
                (accrual_id, date, sku, type_id, type_name, amount)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (accrual_id, date_str, sku, tid,
                  types.get(tid, f"type_{tid}"), amt))
            n_svc += 1

    # item_fees / non_item_fee / container_fees
    for block_name in ("item_fees", "non_item_fee", "container_fees"):
        block = acc.get(block_name)
        if not block:
            continue
        items = block if isinstance(block, list) else [block]
        for it in items:
            tid = it.get("type_id")
            amt = to_float(it.get("accrued")) or to_float(it)
            if tid is None or amt is None:
                continue
            cur.execute("""
                INSERT INTO accruals_services
                (accrual_id, date, sku, type_id, type_name, amount)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (accrual_id, date_str, None, tid,
                  types.get(tid, f"type_{tid}"), amt))
            n_svc += 1

    return n_acc, n_svc

'''

src2, n = pattern.subn(new_func, src)

if n == 0:
    print("[FAIL] Не нашёл save_accrual")
else:
    open("sync_finance.py", "w", encoding="utf-8").write(src2)
    print("[OK] save_accrual перезаписана")
    print("Проверяем синтаксис...")

import py_compile
try:
    py_compile.compile("sync_finance.py", doraise=True)
    print("[OK] Синтаксис валиден")
except py_compile.PyCompileError as e:
    print(f"[FAIL] {e}")
