@echo off
rem Chay backend local: python -m app (doc 06 §5) — http://127.0.0.1:8791/health
cd /d %~dp0backend
if not exist .venv\Scripts\python.exe (
  echo Chua cai moi truong — chay setup-backend.bat truoc.
  pause
  exit /b 1
)
call .venv\Scripts\python.exe -m app
rem Server dung (Ctrl+C / loi) — giu cua so de doc log cuoi
echo.
echo Backend da dung. Log cuoi y tren.
pause
