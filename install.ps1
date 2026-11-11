<#
install.ps1 — установка «Пульта Ozon» на новом компьютере (Windows 10/11, PowerShell 5.1+).

Запуск (из папки проекта):
    powershell -ExecutionPolicy Bypass -File .\install.ps1
или двойной щелчок по install.bat.

Параметры:
    -WithAI          установить локальную ИИ (Ollama и модель из PULT_AI_MODEL)
    -NoTask          не создавать ежедневную задачу в Планировщике
    -TaskTime 09:00  время ежедневного запуска (по умолчанию 09:00)
    -ClientId, -ApiKey, -Sheet   значения для app\.env без вопросов (для повторной установки)

Скрипт можно запускать повторно: существующие app\.env, база и credentials.json не перезаписываются.
Права администратора не нужны.

Шаги: 1) Python  2) библиотеки  3) app\.env  4) ключ Google  5) себестоимость
      6) база данных  7) Планировщик  8) локальная ИИ (по флагу)  9) самопроверка
#>
param(
    [switch]$WithAI,
    [switch]$NoTask,
    [string]$TaskTime = "09:00",
    [string]$ClientId = "",
    [string]$ApiKey = "",
    [string]$Sheet = ""
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location -Path $Root

# UTF-8 для консоли и Python (PowerShell 5.1 по умолчанию работает в cp866/cp1251)
try { chcp 65001 | Out-Null } catch { }
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false) } catch { }
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

$TaskName = "PultOzonDaily"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$script:Warnings = @()

function Step([string]$text) { Write-Host ""; Write-Host "=== $text ===" -ForegroundColor Cyan }
function Ok([string]$text)   { Write-Host "  [OK] $text" -ForegroundColor Green }
function Warn([string]$text) { Write-Host "  [--] $text" -ForegroundColor Yellow; $script:Warnings += $text }
function Die([string]$text)  { Write-Host "  [!!] $text" -ForegroundColor Red; exit 1 }

function Read-EnvFile([string]$path) {
    # .env -> хэш-таблица. Читаем как UTF-8; BOM, если он есть, срезаем.
    $map = @{}
    if (-not (Test-Path -LiteralPath $path)) { return $map }
    $text = [System.IO.File]::ReadAllText($path, [System.Text.Encoding]::UTF8).TrimStart([char]0xFEFF)
    foreach ($line in ($text -split "`r?`n")) {
        $line = $line.Trim()
        if (-not $line -or $line.StartsWith("#") -or ($line.IndexOf("=") -lt 1)) { continue }
        $k = $line.Substring(0, $line.IndexOf("=")).Trim()
        $v = $line.Substring($line.IndexOf("=") + 1).Trim().Trim('"').Trim("'")
        $map[$k] = $v
    }
    return $map
}

function Get-SheetId([string]$value) {
    # Принимает ссылку на таблицу или сам ID
    $value = "$value".Trim()
    if ($value -match "/d/([A-Za-z0-9_-]{20,})") { return $Matches[1] }
    if ($value -match "^[A-Za-z0-9_-]{20,}$") { return $value }
    return ""
}

function Read-Secret([string]$prompt) {
    $sec = Read-Host -Prompt $prompt -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr).Trim() }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
}

Write-Host "Установка «Пульт Ozon» в папку: $Root" -ForegroundColor White

# ───────────── 1. Python ─────────────
Step "1/9 Python"
$pyVersion = $null
try { $pyVersion = (& py -3 -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null | Select-Object -First 1) } catch { }
if (-not $pyVersion) {
    Write-Host "  Python не найден (команда py)." -ForegroundColor Red
    Write-Host "  Установите Python 3.12 с https://www.python.org/downloads/windows/"
    Write-Host "  (в установщике оставьте галочку «py launcher») или командой:"
    Write-Host "      winget install -e --id Python.Python.3.12"
    Die "После установки Python откройте новое окно PowerShell и запустите install.ps1 ещё раз."
}
$parts = $pyVersion.Split(".")
if (([int]$parts[0] -lt 3) -or (([int]$parts[0] -eq 3) -and ([int]$parts[1] -lt 11))) {
    Die "Найден Python $pyVersion, нужен 3.11 или новее."
}
Ok "Python $pyVersion"

# ───────────── 2. Библиотеки ─────────────
Step "2/9 Библиотеки Python"
& py -3 -m pip install --disable-pip-version-check -q -r (Join-Path $Root "requirements.txt")
if ($LASTEXITCODE -ne 0) { Die "pip завершился с ошибкой. Проверьте интернет и повторите запуск." }
Ok "библиотеки из requirements.txt установлены"

# ───────────── 3. app\.env ─────────────
Step "3/9 Ключи Ozon и таблица (app\.env)"
$AppDir = Join-Path $Root "app"
if (-not (Test-Path -LiteralPath $AppDir)) { New-Item -ItemType Directory -Path $AppDir -Force | Out-Null }
$EnvPath = Join-Path $AppDir ".env"
$envMap = Read-EnvFile $EnvPath
$isNew = -not (Test-Path -LiteralPath $EnvPath)
$add = New-Object System.Collections.Generic.List[string]

if (-not $envMap.ContainsKey("OZON_CLIENT_ID")) {
    if (-not $ClientId) {
        Write-Host "  Ключи берутся в кабинете Ozon Seller: Настройки -> Seller API -> Сгенерировать ключ."
        $ClientId = (Read-Host -Prompt "  Client ID").Trim()
    }
    if ($ClientId) { $add.Add("OZON_CLIENT_ID=$ClientId") } else { Warn "OZON_CLIENT_ID не задан — впишите его в app\.env" }
} else { Ok "OZON_CLIENT_ID уже есть в app\.env" }

if (-not $envMap.ContainsKey("OZON_API_KEY")) {
    if (-not $ApiKey) { $ApiKey = Read-Secret "  API key (ввод скрыт)" }
    if ($ApiKey) { $add.Add("OZON_API_KEY=$ApiKey") } else { Warn "OZON_API_KEY не задан — впишите его в app\.env" }
} else { Ok "OZON_API_KEY уже есть в app\.env" }

if (-not $envMap.ContainsKey("PULT_SHEET_ID")) {
    $sheetId = Get-SheetId $Sheet
    if (-not $sheetId) {
        Write-Host "  Google-таблица: сделайте копию шаблона (Файл -> Создать копию) и вставьте сюда ссылку на свою копию."
        if (-not $isNew) { Write-Host "  Enter — оставить таблицу, с которой проект работает сейчас." }
        $answer = Read-Host -Prompt "  Ссылка на таблицу или её ID"
        $sheetId = Get-SheetId $answer
        if ($answer -and -not $sheetId) { Warn "Не удалось распознать ID таблицы в «$answer» — впишите PULT_SHEET_ID в app\.env" }
    }
    if ($sheetId) { $add.Add("PULT_SHEET_ID=$sheetId") }
    elseif ($isNew) { Warn "PULT_SHEET_ID не задан — впишите ID своей таблицы в app\.env" }
} else { Ok "PULT_SHEET_ID уже есть в app\.env" }

if ($add.Count -gt 0) {
    # Дописываем только недостающие строки. Файл — UTF-8 БЕЗ BOM (Set-Content -Encoding UTF8 в PS 5.1 ставит BOM).
    $existing = ""
    if (-not $isNew) { $existing = [System.IO.File]::ReadAllText($EnvPath, [System.Text.Encoding]::UTF8).TrimStart([char]0xFEFF) }
    if ($existing -and -not $existing.EndsWith("`n")) { $existing += "`r`n" }
    $newText = $existing + (($add.ToArray()) -join "`r`n") + "`r`n"
    [System.IO.File]::WriteAllText($EnvPath, $newText, $Utf8NoBom)
    Ok ("в app\.env записано: " + (($add.ToArray() | ForEach-Object { $_.Split("=")[0] }) -join ", "))
}

# ───────────── 4. Ключ Google ─────────────
Step "4/9 Доступ к Google Sheets (app\credentials.json)"
$CredPath = Join-Path $AppDir "credentials.json"
if (-not (Test-Path -LiteralPath $CredPath)) {
    Write-Host "  Нужен ключ сервисного аккаунта Google (делается один раз, 5 минут):"
    Write-Host "    1. https://console.cloud.google.com -> создать проект -> включить «Google Sheets API» и «Google Drive API»"
    Write-Host "    2. IAM и администрирование -> Сервисные аккаунты -> Создать -> Ключи -> Добавить ключ -> JSON"
    Write-Host "    3. Скачанный файл указать ниже (или положить в app\credentials.json и запустить установку ещё раз)"
    $src = (Read-Host -Prompt "  Путь к скачанному JSON-файлу (Enter — пропустить)").Trim().Trim('"')
    if ($src -and (Test-Path -LiteralPath $src)) { Copy-Item -LiteralPath $src -Destination $CredPath; Ok "ключ скопирован в app\credentials.json" }
    else { Warn "нет app\credentials.json — без него таблица не обновится" }
}
if (Test-Path -LiteralPath $CredPath) {
    try {
        $cred = [System.IO.File]::ReadAllText($CredPath, [System.Text.Encoding]::UTF8).TrimStart([char]0xFEFF) | ConvertFrom-Json
        Ok "сервисный аккаунт: $($cred.client_email)"
        Write-Host "       Откройте свою таблицу -> «Настройки доступа» -> добавьте этот адрес с ролью «Редактор»." -ForegroundColor White
    } catch { Warn "app\credentials.json не читается как JSON" }
}

# ───────────── 5. Себестоимость ─────────────
Step "5/9 Себестоимость (costs_all.csv)"
$CostsPath = Join-Path $Root "costs_all.csv"
if (Test-Path -LiteralPath $CostsPath) { Ok "costs_all.csv найден" }
else {
    $header = "offer_id;sku;name;category_l2;cost_price;date_from;cost_price_new;date_from_new`r`n"
    [System.IO.File]::WriteAllText($CostsPath, $header, (New-Object System.Text.UTF8Encoding($true)))
    Warn "создан пустой costs_all.csv — заполните артикул, SKU Ozon и закупочную цену (разделитель «;»), затем: py -m unitka.load_costs"
}

# ───────────── 6. База данных ─────────────
Step "6/9 База данных (app\ozon.db)"
foreach ($dir in @("_logs", "_backups")) {
    $p = Join-Path $Root $dir
    if (-not (Test-Path -LiteralPath $p)) { New-Item -ItemType Directory -Path $p -Force | Out-Null }
}
& py -3 -m unitka.init_db
if ($LASTEXITCODE -ne 0) { Die "база не создана (py -m unitka.init_db)" }
Ok "таблицы базы на месте"

# ───────────── 7. Планировщик ─────────────
Step "7/9 Ежедневный запуск (Планировщик заданий)"
if ($NoTask) { Write-Host "  пропущено (-NoTask)" }
else {
    try {
        $runScript = Join-Path $AppDir "run_daily.ps1"
        $action = New-ScheduledTaskAction -Execute "powershell.exe" `
            -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$runScript`"" -WorkingDirectory $Root
        $trigger = New-ScheduledTaskTrigger -Daily -At $TaskTime
        # StartWhenAvailable: если компьютер был выключен в назначенное время — запустить при включении
        $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
            -ExecutionTimeLimit (New-TimeSpan -Hours 2) -MultipleInstances IgnoreNew
        Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
            -Description "Пульт Ozon: ежедневное обновление данных и таблицы" -Force | Out-Null
        Ok "задача «$TaskName» создана: каждый день в $TaskTime (нужны включённый компьютер, вход в систему и VPN)"
    } catch {
        $reason = ("$($_.Exception.Message)" -split "`r?`n")[0]
        Warn "задача в Планировщике не создана ($reason). Запускайте вручную: app\run_daily.ps1"
    }
}

# ───────────── 8. Локальная ИИ ─────────────
Step "8/9 Локальная ИИ (Ollama)"
if (-not $WithAI) { Write-Host "  пропущено. Сводка «финдиректор» работает и без ИИ; для режима «наставник»: install.ps1 -WithAI" }
else {
    $model = (& py -3 -c "from unitka import config; print(config.AI_MODEL)" | Select-Object -First 1)
    try {
        $ramGb = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
        if ($ramGb -lt 8) { Warn "оперативной памяти $ramGb ГБ — модель будет работать медленно (желательно от 8 ГБ)" }
    } catch { }
    if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
        if (Get-Command winget -ErrorAction SilentlyContinue) {
            Write-Host "  Устанавливаю Ollama через winget..."
            & winget install -e --id Ollama.Ollama --accept-source-agreements --accept-package-agreements
            $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
        }
    }
    if (Get-Command ollama -ErrorAction SilentlyContinue) {
        Write-Host "  Скачиваю модель $model (около 2 ГБ для qwen2.5:3b-instruct)..."
        & ollama pull $model
        if ($LASTEXITCODE -eq 0) { Ok "модель $model установлена" } else { Warn "модель $model не скачалась: ollama pull $model" }
    } else {
        Warn "Ollama не установлена. Скачайте с https://ollama.com/download/windows и повторите: install.ps1 -WithAI"
    }
}

# ───────────── 9. Самопроверка ─────────────
Step "9/9 Самопроверка"
& py -3 -m unitka.doctor
$doctorCode = $LASTEXITCODE

Write-Host ""
if (($doctorCode -eq 0) -and ($script:Warnings.Count -eq 0)) {
    Write-Host "УСТАНОВКА ЗАВЕРШЕНА." -ForegroundColor Green
} else {
    Write-Host "УСТАНОВКА ЗАВЕРШЕНА С ЗАМЕЧАНИЯМИ:" -ForegroundColor Yellow
    foreach ($w in $script:Warnings) { Write-Host "  - $w" -ForegroundColor Yellow }
    if ($doctorCode -ne 0) { Write-Host "  - самопроверка нашла ошибки (строки [!!] выше)" -ForegroundColor Yellow }
}
Write-Host ""
Write-Host "Что дальше:"
Write-Host "  1. Заполнить costs_all.csv и загрузить себестоимость:   py -m unitka.load_costs"
Write-Host "  2. Заполнить лист «НАСТРОЙКИ» в таблице (налог, деньги на счёте, план)"
Write-Host "  3. Первый запуск вручную (нужен VPN):                    .\app\run_daily.ps1"
Write-Host "  4. Проверить установку в любой момент:                  py -m unitka.doctor"
exit $doctorCode
