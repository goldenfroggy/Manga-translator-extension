@echo off
rem Chay backend local: http://127.0.0.1:8791/health
rem Dung Python local backend\runtime\ (tu tai + tu cai deps neu thieu) - khong can cai Python.
cd /d %~dp0
call backend\ensure-runtime.bat
if errorlevel 1 (pause & exit /b 1)

rem Kiem tra bang import that (khong phu thuoc duong dan site-packages)
"%PY%" -c "import uvicorn, fastapi" >nul 2>nul
if errorlevel 1 (
  echo [backend] Thieu deps - dang chay setup-backend.bat ^(lan dau co the mat vai phut^)...
  call setup-backend.bat
  if errorlevel 1 (pause & exit /b 1)
)
cd /d "%~dp0backend"
rem Python embeddable = isolated mode: `python -m app` khong thay package app -> dung launcher
"%PY%" "%~dp0backend\run_app.py"
rem Server dung (Ctrl+C / loi) - giu cua so de doc log cuoi
echo.
echo Backend da dung. Log cuoi y tren.
pause
