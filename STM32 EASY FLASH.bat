@echo off
title STM32 EASY FLASH
cd /d "%~dp0"

echo ========================================
echo  STM32 EASY FLASH Launcher
echo ========================================
echo.

REM Launch PowerShell GUI directly (native Windows, no Python needed)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0flash_gui.ps1"

if %ERRORLEVEL% neq 0 (
    echo.
    echo [INFO] If the GUI didn't open, try running this as Administrator.
    echo       Or run this command in PowerShell:
    echo       powershell -ExecutionPolicy Bypass -File "%~dp0flash_gui.ps1"
    pause
)
