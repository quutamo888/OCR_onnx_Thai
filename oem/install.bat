@echo off
setlocal enabledelayedexpansion

:: Log all output to C:\OEM\install.log
set "LOG=C:\OEM\install.log"
echo [%DATE% %TIME%] Starting ThaiOCR Worker Unattended Setup... > "%LOG%"

:: 1. Open Windows Firewall Port 8001
echo [%DATE% %TIME%] Configuring Windows Firewall for port 8001... >> "%LOG%"
netsh advfirewall firewall delete rule name="ThaiOCR Worker" >nul 2>&1
netsh advfirewall firewall add rule name="ThaiOCR Worker" dir=in action=allow protocol=TCP localport=8001 >> "%LOG%" 2>&1

:: 2. Download Python 3.11 Installer
echo [%DATE% %TIME%] Downloading Python 3.11.9... >> "%LOG%"
curl.exe -L -k -o C:\OEM\python-installer.exe https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe >> "%LOG%" 2>&1

:: 3. Install Python 3.11 Silently
echo [%DATE% %TIME%] Installing Python 3.11... >> "%LOG%"
C:\OEM\python-installer.exe /quiet InstallAllUsers=1 PrependPath=1 Include_test=0 SimpleInstall=1 >> "%LOG%" 2>&1

:: Wait for installer to finish
timeout /t 10 /nobreak >nul

:: 4. Install Dependencies
echo [%DATE% %TIME%] Installing Python packages (FastAPI, Uvicorn, Pillow, PyMuPDF)... >> "%LOG%"
if exist "C:\Program Files\Python311\python.exe" (
    "C:\Program Files\Python311\python.exe" -m pip install --upgrade pip >> "%LOG%" 2>&1
    "C:\Program Files\Python311\python.exe" -m pip install --no-cache-dir fastapi uvicorn pillow pymupdf >> "%LOG%" 2>&1
) else (
    echo [ERROR] Python 3.11 path not found after install >> "%LOG%"
)

:: 5. Setup Auto-start on boot
echo [%DATE% %TIME%] Registering Startup script... >> "%LOG%"
copy /Y "C:\OEM\run_ocr_worker.bat" "%ProgramData%\Microsoft\Windows\Start Menu\Programs\StartUp\run_ocr_worker.bat" >> "%LOG%" 2>&1

:: 6. Launch Worker immediately
echo [%DATE% %TIME%] Launching OCR Worker... >> "%LOG%"
start "ThaiOCR Worker" cmd /c "%ProgramData%\Microsoft\Windows\Start Menu\Programs\StartUp\run_ocr_worker.bat"

echo [%DATE% %TIME%] Setup completed successfully. >> "%LOG%"
exit /b 0
