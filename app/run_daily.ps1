chcp 65001 | Out-Null
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

# Папка проекта = на уровень выше этого файла (app\run_daily.ps1); путь больше не зашит.
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $ProjectRoot "_logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
$ts  = Get-Date -Format yyyyMMdd_HHmmss
$log = Join-Path $logDir "daily_update_$ts.log"

& (Join-Path $PSScriptRoot "daily_update.ps1") *>&1 |
    Tee-Object -FilePath $log

exit $LASTEXITCODE