src = open("sheets_sync.py", encoding="utf-8").read()

# Добавляем import re в начало (после import os)
if "\nimport re\n" not in src:
    src = src.replace(
        "import os\nimport sqlite3",
        "import os\nimport re\nimport sqlite3",
        1
    )
    open("sheets_sync.py", "w", encoding="utf-8").write(src)
    print("[OK] import re добавлен")
else:
    print("[i] import re уже есть")
