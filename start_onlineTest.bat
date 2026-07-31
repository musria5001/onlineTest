@echo off
setlocal

set "ONLINETEST_USE_SQLITE=1"
set "ONLINETEST_DEBUG=1"
set "ONLINETEST_LOCAL_DEV=1"
set "DJANGO_SETTINGS_MODULE=onlineTest.local_settings"
set "PROJECT_DIR=%~dp0"
set "CONDA_PREFIX=C:\Users\hjy\miniconda3\envs\onlineTest_py36"
set "PATH=%CONDA_PREFIX%;%CONDA_PREFIX%\Library\bin;%CONDA_PREFIX%\DLLs;%PATH%"
set "PYTHON_EXE=%CONDA_PREFIX%\python.exe"
set "PORT=8000"

if not exist "%PYTHON_EXE%" (
    echo Python not found: %PYTHON_EXE%
    pause
    exit /b 1
)

start /wait "" "%PYTHON_EXE%" "%PROJECT_DIR%manage.py" migrate --noinput
for /f %%P in ('powershell -NoProfile -Command "$p=8000; while (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue) { $p++ }; Write-Output $p"') do set "PORT=%%P"
start "" /b "%PYTHON_EXE%" "%PROJECT_DIR%manage.py" runserver 127.0.0.1:%PORT% --noreload
timeout /t 5 /nobreak >nul
start "" "http://127.0.0.1:%PORT%/"

endlocal
