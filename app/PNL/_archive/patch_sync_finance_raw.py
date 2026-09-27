"""
patch_sync_finance_raw.py — добавляет raw_json в accruals.
"""
import sqlite3
import os

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(APP_DIR, "ozon.db")

# 1. Добавляем колонку raw_json
con = sqlite3.connect(DB)
cols = [r[1] for r in con.execute("PRAGMA table_info(accruals)")]
if "raw_json" not in cols:
    con.execute("ALTER TABLE accruals ADD COLUMN raw_json TEXT")
    con.commit()
    print("[OK] Колонка raw_json добавлена в accruals")
else:
    print("[i] raw_json уже есть")

if "posting_schema" not in cols:
    con.execute("ALTER TABLE accruals ADD COLUMN posting_schema TEXT")
    con.commit()
    print("[OK] Колонка posting_schema добавлена")
con.close()

# 2. Патч sync_finance.py — сохранять raw
src = open("sync_finance.py", encoding="utf-8").read()

# Заменяем save_accrual
old = '''    for p in products:
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
             seller_price, sale_price, sale_commission, bonus, coinvestment, total_amount)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (accrual_id, date_str, sku, unit, category, schema,
              sp, slp, cm, bn, ci, total))
        n_acc += 1'''

new = '''    # Сохраняем raw JSON для диагностики
    raw_json_str = json.dumps(acc, ensure_ascii=False)

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

    # Если products пустой — сохраняем запись с raw_json и sku=None
    if not products:
        cur.execute("""
            INSERT OR REPLACE INTO accruals
            (accrual_id, date, sku, unit_number, accrued_category, delivery_schema,
             seller_price, sale_price, sale_commission, bonus, coinvestment, total_amount,
             raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (accrual_id, date_str, None, unit, category, schema,
              None, None, None, None, None, total, raw_json_str))
        n_acc += 1'''

if old in src:
    src = src.replace(old, new)
    print("[OK] save_accrual патчен — сохраняет raw_json")
else:
    print("[?] Не нашёл блок save_accrual")

# Добавляем import json если его нет
if "import json" not in src:
    src = src.replace("import os\n", "import os\nimport json\n", 1)
    print("[OK] import json добавлен")

open("sync_finance.py", "w", encoding="utf-8").write(src)
print("\nГотово.")
