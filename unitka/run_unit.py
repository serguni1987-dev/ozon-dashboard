r"""run_unit — одна команда: НАСТРОЙКИ -> API -> лист.

    py run_unit.py              # период из НАСТРОЙКИ
    py run_unit.py --no-load    # только расчёт, без загрузки
    py run_unit.py --local      # в CSV, не в Sheets
    py run_unit.py --force      # перекачать дни
"""
import argparse
import os
import subprocess
import sys
from datetime import date, timedelta

import gspread
from google.oauth2.service_account import Credentials

from . import config, db
from .calc_margin import _to_date_start, _to_date_end


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--no-load", action="store_true")
    p.add_argument("--local",   action="store_true")
    p.add_argument("--force",   action="store_true")
    return p.parse_args()


def read_settings(sh):
    """Возвращает (start, end, tax_rate, raw_b2, raw_b3)."""
    try:
        ws = sh.worksheet(config.SETTINGS_SHEET)
        rows = ws.get("B1:B3")
    except Exception as e:
        print(f"[!] {config.SETTINGS_SHEET}: {e}")
        return None, None, 7.0, None, None

    def cell(r):
        if len(rows) >= r and rows[r - 1] and rows[r - 1][0] not in (None, ""):
            return rows[r - 1][0]
        return None

    tax_raw  = cell(1)
    from_raw = cell(2)
    to_raw   = cell(3)

    tax_rate = 7.0
    if tax_raw is not None:
        try:
            tax_rate = float(str(tax_raw).replace("%", "").replace(",", ".").strip())
        except ValueError:
            pass

    start = _to_date_start(from_raw) if from_raw else None
    end   = _to_date_end(to_raw)     if to_raw   else None

    if not start or not end:
        con = db.connect()
        try:
            row = con.execute("SELECT MAX(date) AS m FROM realization_daily").fetchone()
            last = row["m"] if row and row["m"] else None
        finally:
            con.close()
        if last:
            y, m = map(int, last.split("-")[:2])
            ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
            start = start or f"{y}-{m:02d}-01"
            end   = end   or (date(ny, nm, 1) - timedelta(days=1)).strftime("%Y-%m-%d")

    return start, end, tax_rate, from_raw, to_raw


def run_subprocess(args):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["UNITKA_QUIET"] = "1"   # calc_margin не печатает своё "ГОТОВО"
    r = subprocess.run(args, cwd=str(config.PROJECT), env=env)
    return r.returncode == 0


def main():
    args = parse_args()

    print("=" * 80)
    print("RUN_UNIT — загрузка юнитки + расчёт")
    print("=" * 80)

    scopes = ["https://www.googleapis.com/auth/spreadsheets",
              "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(str(config.CREDENTIALS), scopes=scopes)
    sh = gspread.authorize(creds).open_by_key(config.SHEET_ID)

    start, end, tax_rate, raw_b2, raw_b3 = read_settings(sh)

    if not start or not end:
        print("\n[!] Не удалось определить период.")
        print("    Проверь лист НАСТРОЙКИ (B2 — от, B3 — до).")
        print("    Можно поставить 'auto' — возьмётся последний месяц с данными.")
        sys.exit(1)

    print(f"\nНАСТРОЙКИ: B1={tax_rate}%, B2={raw_b2!r}, B3={raw_b3!r}")
    print(f"Итоговый период: {start} .. {end}")

    if not args.no_load:
        print("\n>>> ЗАГРУЗКА СЕБЕСТОИМОСТИ (costs_all.csv)")
        cmd = [sys.executable, "-B", "-m", "unitka.load_costs"]
        if not run_subprocess(cmd):
            print("\n[!] Ошибка загрузки себестоимости. Прерываю.")
            sys.exit(1)

        print("\n>>> ЗАГРУЗКА РЕАЛИЗАЦИИ")
        cmd = [sys.executable, "-B", "-m", "unitka.load_realization_daily",
               "--from", start, "--to", end]
        if args.force:
            cmd.append("--force")
        if not run_subprocess(cmd):
            print("\n[!] Ошибка загрузки. Прерываю.")
            sys.exit(1)

        print("\n>>> ЗАГРУЗКА ОТПРАВЛЕНИЙ FBS (API v3)")
        cmd = [sys.executable, "-B", "-m", "unitka.load_postings",
               "--from", start, "--to", end]
        if not run_subprocess(cmd):
            print("\n[!] Ошибка загрузки FBS. Прерываю.")
            sys.exit(1)

        print("\n>>> ЗАГРУЗКА ОТПРАВЛЕНИЙ FBO (API v2)")
        cmd = [sys.executable, "-B", "-m", "unitka.load_postings_fbo",
               "--from", start, "--to", end]
        if not run_subprocess(cmd):
            print("\n[!] Ошибка загрузки FBO. Прерываю.")
            sys.exit(1)

    print("\n>>> РАСЧЁТ ЮНИТ-ЭКОНОМИКИ")
    cmd = [sys.executable, "-B", "-m", "unitka.calc_margin"]
    if args.local:
        cmd.append("--local")
    if not run_subprocess(cmd):
        sys.exit(1)

    print("\n" + "=" * 80)
    print("ГОТОВО.")
    if not args.local:
        print(f"https://docs.google.com/spreadsheets/d/{config.SHEET_ID}/edit")
    print("=" * 80)


if __name__ == "__main__":
    main()
