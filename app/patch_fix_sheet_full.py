src = open("PNL/fix_sheet_full.py", encoding="utf-8").read()

src = src.replace(
    'os.path.dirname(os.path.abspath(__file__))',
    'os.path.dirname(os.path.dirname(os.path.abspath(__file__)))',
    1
)

if "import sync_pnl" in src and "sys.path.insert" not in src:
    src = src.replace(
        "import sync_pnl",
        "import sys as _sys\n"
        "import os as _os\n"
        "_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))\n"
        "import sync_pnl",
        1
    )

open("PNL/fix_sheet_full.py", "w", encoding="utf-8").write(src)
print("[OK] fix_sheet_full.py пропатчен")