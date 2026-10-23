@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo       ThaiOCR Windows Worker Service Launcher
echo ========================================================

:: Wait for Z: drive (mounted from Ubuntu host /shared)
echo Waiting for Z: drive connection from host...
:WAIT_SHARE
if not exist "Z:\ocr_worker.py" (
    echo Z:\ocr_worker.py not available yet, waiting 3s...
    timeout /t 3 /nobreak >nul
    goto WAIT_SHARE
)
echo Connected to Z:\ (Shared directory ready).

:: Locate Python executable
set "PY_EXE="
if exist "C:\Program Files\Python311\python.exe" (
    set "PY_EXE=C:\Program Files\Python311\python.exe"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "PY_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
) else (
    for /f "tokens=*" %%i in ('where python 2^>nul') do (
        set "PY_EXE=%%i"
        goto FOUND_PY
    )
)
:FOUND_PY

if "%PY_EXE%"=="" (
    echo [ERROR] Python not found in standard paths. Retrying in 10s...
    timeout /t 10 /nobreak >nul
    goto WAIT_SHARE
)

echo [OK] Using Python: %PY_EXE%
cd /d Z:\

:: Run OCR worker service loop (auto-restart if crashed)
:RUN_LOOP
echo [INFO] Starting OCR Worker on port 8001 at %TIME%...
"%PY_EXE%" ocr_worker.py
echo [WARN] OCR Worker exited with code %ERRORLEVEL%. Restarting in 5s...
timeout /t 5 /nobreak >nul
goto RUN_LOOP
