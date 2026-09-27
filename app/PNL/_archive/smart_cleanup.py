"""smart_cleanup: перемещает временные скрипты из app/ в архивы."""
import os, shutil, re

APP = "."
ARCHIVE = os.path.join("PNL", "_archive")
DIAG    = os.path.join("PNL", "_diag")

os.makedirs(ARCHIVE, exist_ok=True)
os.makedirs(DIAG, exist_ok=True)

# Файлы, которые НЕ трогаем (вызывает run.py или нужны для работы)
KEEP = {
    "run.py", "parse_xlsx.py",
    "sync_monthly.py", "sync_finance.py",
    "fetch_current_prices.py", "fetch_current_stocks.py",
    "sync_archived.py",
    "mark_brands.py", "check_costs_alert.py",
    "sync_decisions.py", "sheets_sync.py",
    "daily_dashboard.py", "decision_effects.py",
    "backup_db.py",
    "import_costs.py", "export_all_costs.py",
    "create_cost_history.py", "migrate_costs_csv.py",
    "install_task.ps1",
    "smart_cleanup.py",
}

# Папки, которые не трогаем
KEEP_DIRS = {"PNL", "Себестоимость", "__pycache__", ".git"}

# Что куда
def classify(name):
    if name in KEEP:
        return None
    if name.startswith("patch_") or name.startswith("fix_"):
        return "archive"
    if name.startswith("check_") or name.startswith("diag_") or name.startswith("peek_"):
        return "diag"
    if name.startswith("restore_") or name.startswith("rewrite_") or name.startswith("reset_"):
        return "archive"
    if name.startswith("add_") or name.startswith("apply_"):
        return "archive"
    if name in ("noop.py", "query.py", "diagnose.py", "cleanup_dead.py",
                "clean_months.py", "clear_august.py", "clear_realization.py",
                "load_all_months.py", "recreate_monthly_tables.py",
                "reorder_tabs.py", "rollback_pnl.py", "plan_core.py",
                "worklist.py", "final_summary.py", "full_audit.py",
                "split_on_account.py", "hot_carts.py", "move_downloads.py",
                "test_tls.py", "diagnose.py"):
        return "archive"
    return None  # неизвестное — оставляем на месте


moved_a = moved_d = 0
for name in sorted(os.listdir(APP)):
    path = os.path.join(APP, name)
    if os.path.isdir(path):
        if name in KEEP_DIRS: continue
        continue
    if not (name.endswith(".py") or name.endswith(".ps1")): continue

    action = classify(name)
    if action == "archive":
        shutil.move(path, os.path.join(ARCHIVE, name))
        moved_a += 1
        print(f"  [ARCH] {name}")
    elif action == "diag":
        shutil.move(path, os.path.join(DIAG, name))
        moved_d += 1
        print(f"  [DIAG] {name}")

print()
print(f"Перемещено в _archive/: {moved_a}")
print(f"Перемещено в _diag/:    {moved_d}")
print()
print("Осталось в app/:")
for name in sorted(os.listdir(APP)):
    if os.path.isfile(os.path.join(APP, name)) and (name.endswith(".py") or name.endswith(".ps1")):
        print(f"  {name}")
