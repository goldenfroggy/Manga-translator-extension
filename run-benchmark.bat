@echo off
rem Chay benchmark voi Python co deps — uu tien backend\.venv (may dev),
rem khong thi dung Python local backend\runtime\ (tu tai neu chua co, khong can cai Python).
cd /d %~dp0
set "PYVENV=%~dp0backend\.venv\Scripts\python.exe"
if exist "%PYVENV%" (
  set "PY=%PYVENV%"
) else (
  call backend\ensure-runtime.bat
  if errorlevel 1 (pause & exit /b 1)
  if not exist "%~dp0backend\runtime\Lib\site-packages\psutil" (
    echo Chua cai deps — chay setup-backend.bat truoc.
    pause
    exit /b 1
  )
)
"%PY%" scripts\benchmark.py %*
if errorlevel 1 (
  echo.
  echo Benchmark thoat voi ma loi %errorlevel% — xem thong bao ben tren.
  pause
  exit /b %errorlevel%
)
