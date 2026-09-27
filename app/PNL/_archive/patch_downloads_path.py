"""
patch_downloads_path.py — обновляет путь к downloads/ в parse_xlsx.py и run.py.
"""
# 1. parse_xlsx.py
src = open("parse_xlsx.py", encoding="utf-8").read()

old = 'DOWNLOADS_DIR = "downloads"'
new = '''_APP_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.dirname(_APP_DIR)
DOWNLOADS_DIR = os.path.join(_ROOT_DIR, "downloads")'''

if old in src:
    src = src.replace(old, new, 1)
    open("parse_xlsx.py", "w", encoding="utf-8").write(src)
    print("[OK] parse_xlsx.py: DOWNLOADS_DIR теперь в корне")
else:
    print("[i] parse_xlsx.py: не нашёл DOWNLOADS_DIR = 'downloads'")

# 2. run.py
src = open("run.py", encoding="utf-8").read()

old = 'DOWNLOADS_DIR = "downloads"'
new = '''_APP_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.dirname(_APP_DIR)
DOWNLOADS_DIR = os.path.join(_ROOT_DIR, "downloads")'''

if old in src:
    src = src.replace(old, new, 1)
    open("run.py", "w", encoding="utf-8").write(src)
    print("[OK] run.py: DOWNLOADS_DIR теперь в корне")
else:
    print("[i] run.py: не нашёл DOWNLOADS_DIR = 'downloads'")
