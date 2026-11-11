@echo off
cd /d "%~dp0app"

echo ============================================================
echo   ????? OZON - ??????
echo ============================================================
echo.

py run.py

echo.
echo ============================================================
echo   ???????? Google Sheets...
echo ============================================================
pushd "%~dp0"
for /f "delims=" %%i in ('py -c "from unitka import config; print(config.SHEET_ID)"') do set SHEET_ID=%%i
popd
start "" "https://docs.google.com/spreadsheets/d/%SHEET_ID%/edit"

echo.
echo === ?????? ===
pause
