@echo off
setlocal enabledelayedexpansion

echo ====================================================================
echo      ThaiOCR Worker - Windows Firewall Permit-IP Configuration
echo ====================================================================

:: Check for admin privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] กรุณาคลิกขวาแล้วเลือก "Run as administrator" เพื่อตั้งค่า Firewall
    pause
    exit /b 1
)

set "UBUNTU_IP=%~1"
if "%UBUNTU_IP%"=="" (
    set /p "UBUNTU_IP=กรุณาระบุ IP Address ของ Ubuntu Server (เช่น 192.168.1.100): "
)

if "%UBUNTU_IP%"=="" (
    echo [ERROR] ไม่ได้ระบุ IP Address ขอยกเลิกการทำงาน
    pause
    exit /b 1
)

echo.
echo กำลังตั้งค่า Windows Firewall สำหรับ Port 8001...
echo อนุญาตเฉพาะ IP: %UBUNTU_IP% และ 127.0.0.1 (Localhost) เท่านั้น
echo IP อื่นๆ ทั้งหมดในเครือข่ายจะถูก Block 100%%
echo.

:: 1. ลบ Rule เก่าที่มีอยู่เดิม
netsh advfirewall firewall delete rule name="ThaiOCR Worker" >nul 2>&1
netsh advfirewall firewall delete rule name="ThaiOCR Worker - Permit Ubuntu Only" >nul 2>&1

:: 2. เพิ่ม Rule ใหม่แบบระบุ Remote IP เจาะจง
netsh advfirewall firewall add rule name="ThaiOCR Worker - Permit Ubuntu Only" dir=in action=allow protocol=TCP localport=8001 remoteip=%UBUNTU_IP%,127.0.0.1 description="Allow ThaiOCR Worker from Ubuntu Server Only"

if %errorlevel% equ 0 (
    echo [OK] ตั้งค่า Windows Firewall สำเร็จ!
    echo.
    echo ตรวจสอบสถานะ Rule:
    netsh advfirewall firewall show rule name="ThaiOCR Worker - Permit Ubuntu Only"
) else (
    echo [FAILED] เกิดข้อผิดพลาดในการตั้งค่า Firewall
)

echo.
echo ====================================================================
pause
