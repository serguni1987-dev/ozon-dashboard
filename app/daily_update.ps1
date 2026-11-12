# Переход в рабочую папку: проект = папка на уровень выше этого файла (app\daily_update.ps1).
# Раньше путь был зашит (C:\Users\sergu\Desktop\проект) — скрипт не работал из другой папки.
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -Path $ProjectRoot

# === CHARSET: UTF-8 для Python и консоли (PS 5.1 не наследует [Console]::OutputEncoding) ===
chcp 65001 | Out-Null
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

# === LOCK FILE: защита от параллельного запуска (PID-based) ===
$lockPath = Join-Path $ProjectRoot "app\daily_update.lock"
if (Test-Path $lockPath) {
    $lockPid = (Get-Content $lockPath -ErrorAction SilentlyContinue | Select-Object -First 1)
    $alive = $false
    if ($lockPid -match '^\d+$') {
        $alive = [bool](Get-Process -Id ([int]$lockPid) -ErrorAction SilentlyContinue)
    }
    if ($alive) {
        Write-Host "daily_update.ps1 уже выполняется (PID $lockPid). Выход." -ForegroundColor Yellow
        exit 1
    } else {
        Write-Host "Устаревший lock (PID $lockPid не жив). Удаляю." -ForegroundColor Yellow
        Remove-Item $lockPath -Force -ErrorAction SilentlyContinue
    }
}
$PID | Set-Content -LiteralPath $lockPath -Encoding UTF8

# === HELPERS ===
function Assert-Vpn {
    param([int]$WaitSeconds = 30)
    $hosts = @(
        @{ Host = "oauth2.googleapis.com"; Port = 443 },
        @{ Host = "api-seller.ozon.ru";   Port = 443 },
        @{ Host = "sheets.googleapis.com"; Port = 443 }
    )
    foreach ($h in $hosts) {
        $ok = Test-NetConnection -ComputerName $h.Host -Port $h.Port -InformationLevel Quiet -WarningAction SilentlyContinue
        if (-not $ok) {
            ipconfig /flushdns | Out-Null
            Write-Host "  [VPN] $($h.Host):$($h.Port) недоступен — flushdns + пауза $WaitSeconds сек..." -ForegroundColor Yellow
            Start-Sleep -Seconds $WaitSeconds
            $ok = Test-NetConnection -ComputerName $h.Host -Port $h.Port -InformationLevel Quiet -WarningAction SilentlyContinue
            if (-not $ok) { throw "VPN недоступен: $($h.Host):$($h.Port)" }
            Write-Host "  [VPN] восстановился, продолжаем." -ForegroundColor Green
        }
    }
}
function Invoke-PyRetry {
    param([string]$Module, [string[]]$PyArgs = @(), [int]$MaxAttempts = 3, [int]$DelaySeconds = 65)
    for ($i = 1; $i -le $MaxAttempts; $i++) {
        & py -m $Module @PyArgs 2>&1 | ForEach-Object { Write-Host $_ }
        $code = $LASTEXITCODE
        Write-Host "  [exit=$code] py -m $Module" -ForegroundColor DarkGray
        if ($code -eq 0) { return $true }
        if ($i -lt $MaxAttempts) {
            ipconfig /flushdns | Out-Null
            Write-Host "  [retry $i/$MaxAttempts] $Module — exit=$code, flushdns + пауза $DelaySeconds сек..." -ForegroundColor Yellow
            Start-Sleep -Seconds $DelaySeconds
            Assert-Vpn
        }
    }
    Write-Host "  [FAIL] $Module после $MaxAttempts попыток" -ForegroundColor Red
    return $false
}
 
function Invoke-CmdRetry {
    param([string]$Command, [string[]]$CmdArgs = @(), [int]$MaxAttempts = 3, [int]$DelaySeconds = 65)
    for ($i = 1; $i -le $MaxAttempts; $i++) {
        & $Command @CmdArgs 2>&1 | ForEach-Object { Write-Host $_ }
        $code = $LASTEXITCODE
        Write-Host "  [exit=$code] $Command $($CmdArgs -join ' ')" -ForegroundColor DarkGray
        if ($code -eq 0) { return $true }
        if ($i -lt $MaxAttempts) {
            ipconfig /flushdns | Out-Null
            Write-Host "  [retry $i/$MaxAttempts] $Command — exit=$code, flushdns + пауза $DelaySeconds сек..." -ForegroundColor Yellow
            Start-Sleep -Seconds $DelaySeconds
            Assert-Vpn
        }
    }
    Write-Host "  [FAIL] $Command $($CmdArgs -join ' ') после $MaxAttempts попыток" -ForegroundColor Red
    return $false
}

Write-Host "=== СТАРТ ОБНОВЛЕНИЯ: $(Get-Date) ===" -ForegroundColor Cyan

# === ПРОВЕРКА VPN ===
Write-Host "Проверка VPN..." -ForegroundColor Cyan
$pingResult = Test-NetConnection -ComputerName oauth2.googleapis.com -Port 443 -WarningAction SilentlyContinue
if (-not $pingResult.TcpTestSucceeded) {
    Write-Host "VPN НЕ РАБОТАЕТ!" -ForegroundColor Red
    Write-Host "Включите VPN и перезапустите daily_update.ps1." -ForegroundColor Yellow
    Write-Host "Скрипт остановлен." -ForegroundColor Yellow
    exit 1
}
Write-Host "VPN работает, продолжаем." -ForegroundColor Green

# === 0. ЗАГРУЗКА ДАННЫХ ИЗ OZON API (до расчётов, чтобы все листы считались по свежей базе) ===
Write-Host "[0/14] Загрузка начислений, отправлений, цен и остатков из Ozon..." -ForegroundColor Yellow
$FromDate = (Get-Date).AddDays(-7).ToString("yyyy-MM-dd")
$ToDate = Get-Date -Format "yyyy-MM-dd"
py -m unitka.load_realization_daily --from $FromDate --to $ToDate --force
py -m unitka.load_postings --from $FromDate --to $ToDate
# Текущие цены и остатки нужны для «МИН. ЦЕНЫ» (Юнит-сводка, Юнит экономика, ПУЛЬТ).
Set-Location (Join-Path $ProjectRoot "app")
if (-not (Invoke-CmdRetry "py" @("fetch_current_prices.py") -MaxAttempts 1)) {
    Write-Host "  Цены не обновлены — мин. цены сравниваются со старой ценой." -ForegroundColor Yellow
}
if (-not (Invoke-CmdRetry "py" @("fetch_current_stocks.py") -MaxAttempts 1)) {
    Write-Host "  Остатки не обновлены." -ForegroundColor Yellow
}
Set-Location $ProjectRoot

# === 1. P&L ===
Write-Host "[1/14] P&L (старый пайплайн)..." -ForegroundColor Yellow
Set-Location (Join-Path $ProjectRoot "app")
$step1ok = $true
if (-not (Invoke-CmdRetry "py" @("sync_finance.py")))          { $step1ok = $false }
if (-not (Invoke-CmdRetry "py" @("sync_monthly.py")))          { $step1ok = $false }
if (-not (Invoke-CmdRetry "py" @("PNL\sync_pnl.py", "$((Get-Date).Year)")))  { $step1ok = $false }
if (-not (Invoke-CmdRetry "py" @("PNL\pnl_format.py")))        { $step1ok = $false }
if (-not (Invoke-CmdRetry "py" @("PNL\fix_sheet_full.py")))    { $step1ok = $false }
if (-not $step1ok) {
    Write-Host "  Шаг 1 завершился с ошибками — продолжаем." -ForegroundColor Yellow
}

# === 2. ФИНАНСОВЫЙ ПАЙПЛАЙН ===
Write-Host "[2/14] Финансовый пайплайн (unitka)..." -ForegroundColor Yellow
Set-Location $ProjectRoot
if (-not (Invoke-PyRetry "unitka.run_finance" @("--days","7"))) {
    Write-Host "  run_finance пропущен после повторов." -ForegroundColor Red
}


# === 3. КОНТЕНТ-РЕЙТИНГИ ===
Write-Host "[3/14] Загрузка контент-рейтингов..." -ForegroundColor Yellow
py -m unitka.load_ratings

# === 4. СЕЗОННОСТЬ ===
Write-Host "[4/14] Анализ сезонности..." -ForegroundColor Yellow
py -m unitka.calc_seasonality

# === 5. ПРОГНОЗ ===
Write-Host "[5/14] Прогноз продаж..." -ForegroundColor Yellow
py -m unitka.calc_forecast

# === 6. РЕКОМЕНДАЦИИ ПО ЗАКУПКАМ ===
Write-Host "[6/14] Рекомендации по закупкам..." -ForegroundColor Yellow
py -m unitka.calc_recommendations

# === 7. АНАЛИТИКА + ПУЛЬТ ===
Write-Host "[7/14] Аналитический пайплайн (воронка, ПУЛЬТ)..." -ForegroundColor Yellow
if (-not (Invoke-PyRetry "unitka.run_analytics")) {
    Write-Host "  unitka.run_analytics пропущен после повторов." -ForegroundColor Red
}

# === 8. ЖУРНАЛ ИЗМЕНЕНИЙ ===
Write-Host "[8/14] Журнал изменений..." -ForegroundColor Yellow
if (-not (Invoke-PyRetry "unitka.calc_change_log")) {
    Write-Host "  unitka.calc_change_log пропущен после повторов." -ForegroundColor Red
}

# === 9. ЗАГРУЗКА ВОЗВРАТОВ ===
Write-Host "[9/14] Загрузка возвратов..." -ForegroundColor Yellow
py -m unitka.load_returns

# === 10. АНАЛИЗ ВОЗВРАТОВ ===
Write-Host "[10/14] Анализ возвратов..." -ForegroundColor Yellow
if (-not (Invoke-PyRetry "unitka.calc_returns")) {
    Write-Host "  unitka.calc_returns пропущен после повторов." -ForegroundColor Red
}

# === 11. ПЛАН/ФАКТ И KPI (до стратегий: стратегии читают лист KPI) ===
Write-Host "[11/14] План/Факт и KPI..." -ForegroundColor Yellow
if (-not (Invoke-PyRetry "unitka.calc_plan_fact")) {
    Write-Host "  unitka.calc_plan_fact пропущен после повторов." -ForegroundColor Red
}

# === 12. СТРАТЕГИИ ===
Write-Host "[12/14] Стратегии..." -ForegroundColor Yellow
if (-not (Invoke-PyRetry "unitka.calc_strategy")) {
    Write-Host "  unitka.calc_strategy пропущен после повторов." -ForegroundColor Red
}

# === 13. БЭКАП БД ===
Write-Host "[13/14] Бэкап БД..." -ForegroundColor Yellow
py -m unitka.backup_db

# === 14. ФИНАЛЬНЫЙ ПУЛЬТ ===

# === ГЕНЕРАЦИЯ УМНОГО ПЛАНА ДЕЙСТВИЙ ===
Write-Host "[New] Генерация умного плана действий..." -ForegroundColor Yellow
py -m unitka.calc_action_plan
Write-Host "[14/14] Финальное обновление ПУЛЬТА..." -ForegroundColor Yellow
if (-not (Invoke-PyRetry "unitka.calc_pulse")) {
    Write-Host "  unitka.calc_pulse пропущен после повторов." -ForegroundColor Red
}


# === АВТОМАТИЧЕСКИЙ РЕПРАЙСИНГ (ПЛАВНЫЙ ШАГ) ===
Write-Host "[New] Запуск динамического репрайсинга..." -ForegroundColor Yellow
python -m unitka.update_min_prices
python -m unitka.auto_repricer --limit 15
Write-Host "=== ГОТОВО: $(Get-Date) ===" -ForegroundColor Green


# === снятие lock ===
Remove-Item $lockPath -Force -ErrorAction SilentlyContinue