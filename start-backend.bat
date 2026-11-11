@echo off
rem Chay backend local: python -m app (doc 06 §5) — http://127.0.0.1:8791/health
rem Dung Python local backend\runtime\ (tu tai neu chua co) — khong can cai Python tren may.
cd /d %~dp0
call backend\ensure-runtime.bat
if errorlevel 1 (pause & exit /b 1)
if not exist "%~dp0backend\runtime\Lib\site-packages\uvicorn" (
  echo Chua cai deps — chay setup-backend.bat truoc.
  pause
  exit /b 1
)
cd backend
rem Python embeddable = isolated mode: `python -m app` khong thay package app -> dung launcher
"%PY%" "%~dp0backend\run_app.py"
rem Server dung (Ctrl+C / loi) — giu cua so de doc log cuoi
echo.
echo Backend da dung. Log cuoi y tren.
pause
