@echo off
rem Khoi tao moi truong backend tren Windows (Python 3.11+)
cd /d %~dp0backend
if not exist .venv (
  echo Tao venv...
  python -m venv .venv || goto :err
)
call .venv\Scripts\activate.bat
rem Cai dep bang requirements.txt (KHONG qua pip install -e — xanh lau loi build/editable)
python -m pip install -q --disable-pip-version-check -r requirements.txt || goto :err
echo.
echo OK - moi truong san sang.
echo   Chay backend  : start-backend.bat
echo   Chay benchmark: run-benchmark.bat
goto :eof

:err
echo.
echo LOI cai dat. Kiem tra:
echo   python -V     (can 3.11+, winget install Python.Python.3.11 neu chua co)
echo   Ket noi mang khi pip cai deps.
pause
exit /b 1
