"""
load_all_months.py - загружает отчёты о реализации с января по сентябрь.
"""
import subprocess
import sys
import os

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

months = ["2026-01", "2026-02", "2026-03", "2026-04",
          "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]

for m in months:
    print(f"\n{'=' * 60}")
    print(f"ЗАГРУЗКА ЗА {m}")
    print("=" * 60)
    r = subprocess.run(
        [PY, "sync_monthly.py", f"--month={m}"],
        cwd=APP_DIR, capture_output=False, text=True,
    )

print("\n[OK] Все месяцы загружены")
