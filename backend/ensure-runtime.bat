@echo off
rem ============ Python runtime local cho backend ============
rem Neu backend\runtime\python.exe chua co (hoac thieu pip): tai Python 3.11
rem "embeddable" (~11MB) tu python.org, bat "import site" de pip chay duoc,
rem roi cai pip. -> May dich KHONG can cai Python; runtime nam trong repo (gitignored).
rem Sau khi chay, bien %PY% tro toi python.exe local cho file .bat goi bang "call".

set "PY=%~dp0runtime\python.exe"
if exist "%PY%" (
  "%PY%" -m pip --version >nul 2>nul
  if not errorlevel 1 exit /b 0
  echo [runtime] Python local co san nhung thieu pip - cai lai tu dau...
  rmdir /s /q "%~dp0runtime"
)

rem Python embeddable chi co ban 64-bit (amd64) - bao ro neu may chay Windows 32-bit
if /i "%PROCESSOR_ARCHITECTURE%"=="AMD64" goto :arch_ok
if /i "%PROCESSOR_ARCHITEW6432%"=="AMD64" goto :arch_ok
echo [runtime] LOI: Windows dang chay 32-bit, Python 64-bit cua backend khong chay duoc.
echo           Can cai Windows 64-bit hoac Python 32-bit thu cong.
pause
exit /b 1
:arch_ok

set "VER=3.11.9"
set "URL=https://www.python.org/ftp/python/%VER%/python-%VER%-embed-amd64.zip"
set "WANT=009D6BF7E3B2DDCA3D784FA09F90FE54336D5B60F0E0F305C37F400BF83CFD3B"
set "ZIP=%TEMP%\python-%VER%-embed.zip"
set "GETPIP=%TEMP%\get-pip.py"

echo [runtime] Tai Python %VER% embeddable (~11MB) tu python.org...
if exist "%~dp0runtime" rmdir /s /q "%~dp0runtime"

curl.exe -f -L -o "%ZIP%" "%URL%"
if errorlevel 1 powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri '%URL%' -OutFile '%ZIP%'"
if errorlevel 1 goto :dl_err

rem Kiem tra SHA256 (cong khai tu python.org) - tranh zip loi/da bi sua
powershell -NoProfile -Command "if ((Get-FileHash '%ZIP%' -Algorithm SHA256).Hash -ne '%WANT%') { exit 1 }"
if errorlevel 1 goto :hash_err

powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Path '%ZIP%' -DestinationPath '%~dp0runtime' -Force"
if errorlevel 1 goto :unzip_err

rem Ban embeddable mac dinh tat "import site" (python311._pth) - bat len de pip chay duoc
powershell -NoProfile -Command "(Get-Content '%~dp0runtime\python311._pth') -replace '#import site','import site' | Set-Content '%~dp0runtime\python311._pth' -Encoding ASCII"

curl.exe -f -L -o "%GETPIP%" https://bootstrap.pypa.io/get-pip.py
if errorlevel 1 goto :dl_err
"%PY%" "%GETPIP%" --no-warn-script-location
if errorlevel 1 goto :pip_err

rem Ca pip cung phai that su chay duoc (bat "import site" that bai se lo ra o day)
"%PY%" -m pip --version >nul 2>nul
if errorlevel 1 goto :pip_err

"%PY%" -c "import sys; print('[runtime] OK -', sys.version.split()[0])"
del "%ZIP%" "%GETPIP%" >nul 2>nul
exit /b 0

:dl_err
echo [runtime] LOI tai Python/get-pip. Kiem tra ket noi mang roi chay lai.
pause
exit /b 1

:hash_err
echo [runtime] LOI: zip tai ve khong khop SHA256 - co the file loi. Chay lai de tai lai.
pause
exit /b 1

:unzip_err
echo [runtime] LOI giai nen zip (PowerShell Expand-Archive).
pause
exit /b 1

:pip_err
echo [runtime] LOI cai pip vao Python local.
pause
exit /b 1
