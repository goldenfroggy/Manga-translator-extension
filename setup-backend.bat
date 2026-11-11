@echo off
rem Khoi tao moi truong backend tren Windows — KHONG can cai Python tren may:
rem tai Python 3.11 local ve backend\runtime\ (ensure-runtime.bat) roi cai deps vao do.
cd /d %~dp0
call backend\ensure-runtime.bat
if errorlevel 1 goto :err
cd backend
"%PY%" -m pip install -q --disable-pip-version-check --no-warn-script-location -r requirements.txt
if errorlevel 1 goto :err
echo.
echo OK - moi truong san sang (Python local: backend\runtime\python.exe).
echo   Chay backend  : start-backend.bat
echo   Chay benchmark: run-benchmark.bat
goto :eof

:err
echo.
echo LOI cai dat. Chay lai file nay de thu lai (phai da tai se duoc tai su dung).
pause
exit /b 1
