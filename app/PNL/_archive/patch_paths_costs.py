"""patch_paths_costs.py — правит пути в 4 ядровых скриптах Себестоимость/.
APP_DIR теперь = app (2 уровня вверх), PROJECT_DIR = проект (3 уровня вверх).
"""
import os, re

COST_DIR = os.path.dirname(os.path.abspath(__file__))   # app
COSTS_SUBDIR = os.path.join(COST_DIR, "Себестоимость")

FILES = [
    "import_costs.py",
    "export_all_costs.py",
    "create_cost_history.py",
    "migrate_costs_csv.py",
]

OLD1 = '''APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(APP_DIR)'''

NEW1 = '''COST_DIR = os.path.dirname(os.path.abspath(__file__))       # app/Себестоимость
APP_DIR = os.path.dirname(COST_DIR)                        # app
PROJECT_DIR = os.path.dirname(APP_DIR)                     # проект'''

OLD2 = '''DB = "ozon.db"
CSV = "costs_all.csv"'''

NEW2 = '''DB = os.path.join(APP_DIR, "ozon.db")
CSV = os.path.join(PROJECT_DIR, "costs_all.csv")'''

OLD3 = '''DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ozon.db")'''
NEW3 = '''DB = os.path.join(APP_DIR, "ozon.db")'''

changed = []
for fname in FILES:
    path = os.path.join(COSTS_SUBDIR, fname)
    if not os.path.exists(path):
        print(f"[!] Нет файла: {fname}")
        continue
    src = open(path, encoding="utf-8").read()
    orig = src
    
    src = src.replace(OLD1, NEW1, 1)
    src = src.replace(OLD2, NEW2, 1)
    src = src.replace(OLD3, NEW3, 1)
    
    # Если APP_DIR не объявлен — добавить в начало после import os
    if "APP_DIR =" not in src:
        src = src.replace(
            "import os\n",
            'import os\nCOST_DIR = os.path.dirname(os.path.abspath(__file__))\nAPP_DIR = os.path.dirname(COST_DIR)\nPROJECT_DIR = os.path.dirname(APP_DIR)\n',
            1
        )
    
    if src != orig:
        open(path, "w", encoding="utf-8").write(src)
        changed.append(fname)
        print(f"[OK] {fname}")
    else:
        print(f"[i] {fname} — не изменено (проверь вручную)")

print(f"\nИзменено: {len(changed)}")