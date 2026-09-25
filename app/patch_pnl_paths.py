"""patch_pnl_paths.py — правит пути в скриптах PNL/ (не трогает _archive).
Делает:
1. APP_DIR = os.path.dirname(os.path.abspath(__file__))
   → os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
2. sqlite3.connect("ozon.db") → абсолютный путь к app\ozon.db
3. load_dotenv() → load_dotenv с явным путём к app\.env
"""
import os

BASE = os.path.dirname(os.path.abspath(__file__))  # = app
PNL = os.path.join(BASE, "PNL")
PARENT = "os.path.dirname(os.path.dirname(os.path.abspath(__file__)))"


def fix_file(path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    orig = src

    # 1) APP_DIR
    src = src.replace(
        "APP_DIR = os.path.dirname(os.path.abspath(__file__))",
        f"APP_DIR = {PARENT}"
    )

    # 2) sqlite3.connect("ozon.db")
    if 'sqlite3.connect("ozon.db")' in src:
        if "import os" not in src:
            src = src.replace("import sqlite3", "import os\nimport sqlite3", 1)
        src = src.replace(
            'sqlite3.connect("ozon.db")',
            f'sqlite3.connect(os.path.join({PARENT}, "ozon.db"))'
        )

    # 3) load_dotenv() без аргумента
    if "load_dotenv()" in src:
        src = src.replace(
            "load_dotenv()",
            f'load_dotenv(os.path.join({PARENT}, ".env"))'
        )

    if src != orig:
        with open(path, "w", encoding="utf-8") as f:
            f.write(src)
        return True
    return False


changed = []
for f in sorted(os.listdir(PNL)):
    if not f.endswith(".py"):
        continue
    path = os.path.join(PNL, f)
    if fix_file(path):
        changed.append(f)

print(f"Пропатчено: {len(changed)} файлов")
for c in changed:
    print(f"  {c}")