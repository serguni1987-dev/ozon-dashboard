@echo off
rem Ustanovka "Pult Ozon": zapuskaet install.ps1 s razresheniem na vypolnenie skripta.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
echo.
pause
