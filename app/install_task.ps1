# install_task.ps1 v3
$TaskName = "OzonMonthlyRitual"
$AppDir   = "C:\Users\sergu\Desktop\проект\app"
$PythonExe = "C:\Users\sergu\AppData\Local\Python\pythoncore-3.14-64\python.exe"

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
