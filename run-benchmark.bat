@echo off
rem Chay benchmark voi Python cua backend\.venv (co san deps) — khong dung python he thong.
cd /d %~dp0
set "PY=%~dp0backend\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo [!] Chua co backend\.venv voi day du deps. Chay "setup-backend.bat" truoc.
  echo     Neu van muon dung Python he thong:
  echo       python -m pip install "numpy<2.3" opencv-python-headless rapidocr onnxruntime psutil
  pause
  exit /b 1
)
"%PY%" scripts\benchmark.py %*
if errorlevel 1 (
  echo.
  echo Benchmark thoat voi ma loi %errorlevel% — xem thong bao ben tren.
  pause
  exit /b %errorlevel%
)
