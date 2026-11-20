@echo off
rem Khoi tao moi truong backend tren Windows - KHONG can cai Python tren may:
rem tai Python 3.11 local ve backend\runtime\ (ensure-runtime.bat) roi cai deps vao do.
rem Neu import that bai (deps hong/thieu DLL) -> tu xoa runtime va cai lai 1 lan.
cd /d %~dp0
set "TRIED_REPAIR="

:retry
call "%~dp0backend\ensure-runtime.bat"
if errorlevel 1 goto :err
cd /d "%~dp0backend"
echo [setup] Cai deps vao %PY% ...
"%PY%" -m pip install -q --disable-pip-version-check --no-warn-script-location -r requirements.txt
if errorlevel 1 goto :err

rem Kiem tra THAT: import duoc het deps chua (bat ca loi thieu DLL VC++ cua onnxruntime)
"%PY%" -c "import fastapi, uvicorn, onnxruntime, rapidocr, cv2, numpy, PIL, psutil, httpx, multipart; print('[deps] import OK')"
if not errorlevel 1 goto :ok

rem import that bai -> lan dau thi xoa Python local cai lai sach (hay gap: dist-info
rem con nhung file package da mat khi pip bi ngat giua chung)
if defined TRIED_REPAIR goto :depcheck_err
set "TRIED_REPAIR=1"
echo.
echo [setup] Import that bai - xoa Python local va cai lai tu dau...
rmdir /s /q "%~dp0backend\runtime"
goto :retry

:ok
echo.
echo OK - moi truong san sang (Python local: backend\runtime\python.exe).
echo   Chay backend  : start-backend.bat
echo   Chay benchmark: run-benchmark.bat
goto :eof

:depcheck_err
echo.
echo LOI: da cai lai sach nhung import van that bai (xem thong bao Python ngay tren).
echo   Python dang dung : %PY%
echo   Go loi thuong gap: thieu "Microsoft Visual C++ Redistributable x64"
echo   -^> cai VC++ Redist x64 tu aka.ms/vs/17/release/vc_redist.x64.exe roi chay lai file nay.
pause
exit /b 1

:err
echo.
echo LOI cai dat. Chay lai file nay de thu lai (phai da tai se duoc tai su dung).
pause
exit /b 1
