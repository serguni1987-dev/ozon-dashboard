@echo off
cd /d "%~dp0"

echo ============================================================
echo   OBNOVLENIE PNL
echo ============================================================
echo.

echo [1/3] Dannye...
py PNL\sync_pnl.py 2026
if errorlevel 1 goto error

echo.
echo [2/3] Stil...
py PNL\pnl_format.py
if errorlevel 1 goto error

echo.
echo [3/3] Formuly...
py PNL\fix_sheet_full.py
if errorlevel 1 goto error

echo.
echo ============================================================
echo   GOTOVO. Otkryvayu tablicu...
echo ============================================================
start "" "https://docs.google.com/spreadsheets/d/1Or2Gak6ihm00rM7ZNF4YvGcEPi6ULLadKIgBjnQZ6q0/edit"
pause
exit /b 0

:error
echo.
echo [OSHIBKA] Skript zavershilsya s oshibkoy.
pause
exit /b 1
