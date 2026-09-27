"""
fix_save_accrual_v2.py — правильный парсинг non_item_fee и item_fees.
"""
import re

src = open("sync_finance.py", encoding="utf-8").read()

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

    # === 1. Основная запись в accruals ===
    # Если есть products — по одной на каждый SKU
    # Если нет — одна запись с sku=None
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
    else:
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

    # === 2. non_item_fee — простой объект ===
    non_item = acc.get("non_item_fee")
    if non_item and isinstance(non_item, dict):
        tid = non_item.get("type_id")
        amt = to_float(non_item.get("accrued"))
        if tid is not None and amt is not None:
            cur.execute("""
                INSERT INTO accruals_services
                (accrual_id, date, sku, type_id, type_name, amount)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (accrual_id, date_str, None, tid,
                  types.get(tid, f"type_{tid}"), amt))
            n_svc += 1

    # === 3. item_fees — вложенная структура fees[].fees[] ===
    item_fees = acc.get("item_fees")
    if item_fees and isinstance(item_fees, dict):
        fee_groups = item_fees.get("fees") or []
        for group in fee_groups:
            sku = group.get("sku")
            inner_fees = group.get("fees") or []
            for fee in inner_fees:
                tid = fee.get("type_id")
                amt = to_float(fee.get("accrued"))
                if tid is None or amt is None:
                    continue
                cur.execute("""
                    INSERT INTO accruals_services
                    (accrual_id, date, sku, type_id, type_name, amount)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (accrual_id, date_str, sku, tid,
                      types.get(tid, f"type_{tid}"), amt))
                n_svc += 1

    # === 4. container_fees — на всякий случай ===
    container = acc.get("container_fees")
    if container and isinstance(container, dict):
        fees = container.get("fees") or []
        for fee in fees:
            tid = fee.get("type_id")
            amt = to_float(fee.get("accrued"))
            if tid is not None and amt is not None:
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

import py_compile
try:
    py_compile.compile("sync_finance.py", doraise=True)
    print("[OK] Синтаксис валиден")
except py_compile.PyCompileError as e:
    print(f"[FAIL] {e}")
