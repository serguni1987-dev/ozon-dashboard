# install_task.ps1 v3
$TaskName = "OzonMonthlyRitual"
# Пути больше не зашиты: папка app — там, где лежит этот файл; Python — тот, что находит лаунчер py.
$AppDir   = $PSScriptRoot
$PythonExe = (& py -c "import sys; print(sys.executable)" 2>$null | Select-Object -First 1)
if (-not $PythonExe) { Write-Error "Python не найден (команда py). Установите Python 3.11+ с python.org."; exit 1 }

if (-not (Test-Path $PythonExe)) {
    Write-Error "Python не найден: $PythonExe"
    exit 1
}

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Error "НЕ АДМИН. Открой PowerShell через правый клик -> Запуск от имени администратора."
    exit 1
}

Write-Host "Python: $PythonExe"
Write-Host "AppDir: $AppDir"
Write-Host ""

$cmd = "`"$PythonExe`" run.py --no-dashboard"
Write-Host "Команда: $cmd"
Write-Host ""

schtasks /Query /TN $TaskName 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Удаляю старую задачу..."
    schtasks /Delete /TN $TaskName /F
}

schtasks /Create `
    /TN $TaskName `
    /TR $cmd `
    /SC MONTHLY `
    /D 10 `
    /ST 10:00 `
    /RL HIGHEST `
    /IT `
    /F

if ($LASTEXITCODE -ne 0) {
    Write-Error "Код: $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "[OK] Задача создана"
Write-Host ""
schtasks /Query /TN $TaskName /V /FO LIST | Select-String "TaskName|Next Run|Status|Task To Run|Schedule|Start"
