@echo off
cd /d "%~dp0app"

echo ============================================================
echo   PNL - PROVERKA TIPOV + OBNOVLENIE
echo ============================================================
echo.

echo [1/4] Proverka type_id...
py PNL\_diag\check_all_types.py
if errorlevel 1 goto error

echo.
echo [2/4] Dannye P^&L...
py PNL\sync_pnl.py 2026
if errorlevel 1 goto error

echo.
echo [3/4] Stil...
py PNL\pnl_format.py
if errorlevel 1 goto error

echo.
echo [4/4] Formuly...
py PNL\fix_sheet_full.py
if errorlevel 1 goto error

echo.
echo ============================================================
echo   GOTOVO
echo ============================================================
pause
exit /b 0

:error
echo.
echo [OSHIBKA] Skript zavershilsya s oshibkoy.
pause
exit /b 1