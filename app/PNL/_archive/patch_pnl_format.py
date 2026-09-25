src = open("PNL/pnl_format.py", encoding="utf-8").read()

# 1) APP_DIR на уровень выше
src = src.replace(
    "APP_DIR = os.path.dirname(os.path.abspath(__file__))",
    "APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))",
    1
)

# 2) sys.path.insert перед import sync_pnl
if "import sync_pnl" in src and "sys.path.insert" not in src:
    src = src.replace(
        "import sync_pnl",
        "import sys as _sys\n"
        "import os as _os\n"
        "_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))\n"
        "import sync_pnl",
        1
    )

open("PNL/pnl_format.py", "w", encoding="utf-8").write(src)
print("[OK] pnl_format.py пропатчен")