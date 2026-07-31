$ErrorActionPreference = "Stop"

$env:ONLINETEST_USE_SQLITE = "1"
$env:ONLINETEST_DEBUG = "1"
$env:ONLINETEST_LOCAL_DEV = "1"
$env:DJANGO_SETTINGS_MODULE = "onlineTest.local_settings"

$env:CONDA_PREFIX = "C:\Users\hjy\miniconda3\envs\onlineTest_py36"
$env:PATH = "$env:CONDA_PREFIX;$env:CONDA_PREFIX\Library\bin;$env:CONDA_PREFIX\DLLs;$env:PATH"

$pythonExe = "$env:CONDA_PREFIX\python.exe"
$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$port = 8000

while (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
    $port++
}

if (-not (Test-Path $pythonExe)) {
    Write-Host "Python not found: $pythonExe"
    exit 1
}

Start-Process -Wait -NoNewWindow -FilePath $pythonExe -ArgumentList "$projectDir\manage.py", "migrate", "--noinput" -WorkingDirectory $projectDir
Start-Process -WindowStyle Hidden -FilePath $pythonExe -ArgumentList "$projectDir\manage.py", "runserver", "127.0.0.1:$port", "--noreload" -WorkingDirectory $projectDir
Start-Sleep -Seconds 3
Start-Process "http://127.0.0.1:$port/"
