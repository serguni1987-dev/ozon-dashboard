@echo off
cd /d "%~dp0app"

echo ============================================================
echo   ????? OZON - ??????
echo ============================================================
echo.

"C:\Users\sergu\AppData\Local\Python\pythoncore-3.14-64\python.exe" run.py

echo.
echo ============================================================
echo   ???????? Google Sheets...
echo ============================================================
start "" "https://docs.google.com/spreadsheets/d/1Or2Gak6ihm00rM7ZNF4YvGcEPi6ULLadKIgBjnQZ6q0/edit"

echo.
echo === ?????? ===
pause
