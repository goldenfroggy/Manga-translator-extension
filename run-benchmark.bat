@echo off
rem Chay benchmark - uu tien backend\.venv (may dev), khong thi Python local backend\runtime\
rem (tu tai + tu cai deps neu thieu - khong can cai Python tren may).
cd /d %~dp0
set "PYVENV=%~dp0backend\.venv\Scripts\python.exe"
if exist "%PYVENV%" (
  set "PY=%PYVENV%"
) else (
  call backend\ensure-runtime.bat
  if errorlevel 1 (pause & exit /b 1)
  rem Kiem tra bang import that (khong phu thuoc duong dan site-packages)
  "%PY%" -c "import psutil, rapidocr, cv2, onnxruntime" >nul 2>nul
  if errorlevel 1 (
    echo [benchmark] Thieu deps - dang chay setup-backend.bat ^(lan dau co the mat vai phut^)...
    call setup-backend.bat
    if errorlevel 1 (pause & exit /b 1)
  )
)
cd /d "%~dp0"
"%PY%" scripts\benchmark.py %*
if errorlevel 1 (
  echo.
  echo Benchmark thoat voi ma loi %errorlevel% - xem thong bao ben tren.
  pause
  exit /b %errorlevel%
)
