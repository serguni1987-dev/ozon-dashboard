from pathlib import Path

path = Path(r"C:\Users\sergu\Desktop\проект\app\daily_update.ps1")
content = path.read_text(encoding="utf-8-sig")

if "load_realization_daily" not in content:
    injection = """
# === ЗАГРУЗКА ДАННЫХ ИЗ OZON API ===
Write-Host "[New] Загрузка начислений и отправлений из Ozon..." -ForegroundColor Yellow
$FromDate = (Get-Date).AddDays(-7).ToString("yyyy-MM-dd")
$ToDate = Get-Date -Format "yyyy-MM-dd"
python -m unitka.load_realization_daily --from $FromDate --to $ToDate --force
python -m unitka.load_postings --from $FromDate --to $ToDate

"""
    target = "# === 3. КОНТЕНТ-РЕЙТИНГИ ==="
    if target in content:
        content = content.replace(target, injection + target)
        path.write_text(content, encoding="utf-8-sig")
        print("УСПЕХ: daily_update.ps1 исправлен! Загрузчики добавлены перед 3-м шагом.")
    else:
        print("ОШИБКА: Не нашел строку '# === 3. КОНТЕНТ-РЕЙТИНГИ ==='")
else:
    print("Загрузчики уже есть в скрипте. Ничего не менял.")