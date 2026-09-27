# fix_workingdir.ps1 — добавить WorkingDirectory к задаче.
# ЗАПУСКАТЬ ОТ АДМИНИСТРАТОРА.

$TaskName = "OzonMonthlyRitual"
$AppDir   = "C:\Users\sergu\Desktop\проект\app"
$PythonExe = "C:\Users\sergu\AppData\Local\Python\pythoncore-3.14-64\python.exe"

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Error "НЕ АДМИН. Открой PowerShell от имени администратора."
    exit 1
}

# XML задачи с рабочей папкой
$xml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Ежемесячный ритуал Ozon: синк данных и пересборка P&amp;L</Description>
    <Author>TERMINATOR\sergu</Author>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>2026-10-10T10:00:00</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByMonth>
        <DaysOfMonth>
          <Day>10</Day>
        </DaysOfMonth>
        <Months>
          <January/><February/><March/><April/><May/><June/>
          <July/><August/><September/><October/><November/><December/>
        </Months>
      </ScheduleByMonth>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>TERMINATOR\sergu</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT2H</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>$PythonExe</Command>
      <Arguments>run.py --no-dashboard</Arguments>
      <WorkingDirectory>$AppDir</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"@

# Сохранить как UTF-16 (требование Task Scheduler)
$xmlPath = Join-Path $env:TEMP "OzonMonthlyRitual.xml"
[System.IO.File]::WriteAllText($xmlPath, $xml, [System.Text.Encoding]::Unicode)

# Удалить старую задачу
schtasks /Delete /TN $TaskName /F 2>$null | Out-Null

# Импортировать новую
schtasks /Create /TN $TaskName /XML $xmlPath /F

if ($LASTEXITCODE -ne 0) {
    Write-Error "Не удалось создать задачу. Код: $LASTEXITCODE"
    exit 1
}

Remove-Item $xmlPath -Force

Write-Host ""
Write-Host "[OK] Задача пересоздана с рабочей папкой"
Write-Host ""
schtasks /Query /TN $TaskName /V /FO LIST | Select-String "Имя задачи|Время следующего|Состояние|Задача для|Рабочая папка|Тип расписания|Время начала|дн\."
