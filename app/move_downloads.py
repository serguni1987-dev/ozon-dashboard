"""
move_downloads.py — переносит downloads/ в корень проекта.
"""
import os
import shutil
from pathlib import Path

APP = Path(".").resolve()
ROOT = APP.parent

OLD = APP / "downloads"
NEW = ROOT / "downloads"


def main():
    if not OLD.exists():
        print(f"[ERROR] Нет папки {OLD}")
        return

    if NEW.exists():
        print(f"[i] {NEW} уже существует — переносим содержимое")
        for f in OLD.iterdir():
            target = NEW / f.name
            if target.exists():
                print(f"  [SKIP] {f.name} — уже есть")
                continue
            shutil.move(str(f), str(target))
            print(f"  [OK] {f.name}")
        try:
            OLD.rmdir()
            print(f"[OK] {OLD} удалена")
        except OSError:
            print(f"[WARN] {OLD} не пуста, оставлена")
    else:
        shutil.move(str(OLD), str(NEW))
        print(f"[OK] {OLD} -> {NEW}")

    print()
    print("Содержимое downloads/:")
    for f in sorted(NEW.iterdir()):
        size = f.stat().st_size // 1024
        print(f"  {f.name}  ({size} КБ)")


if __name__ == "__main__":
    main()
