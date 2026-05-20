@echo off
setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%.."

set "DEFAULT_HEX=%PROJECT_DIR%\build\2026-rov-Float-STM32.hex"
set "HEX_FILE=%~1"

if "%HEX_FILE%"=="" (
    set "HEX_FILE=%DEFAULT_HEX%"
    echo [INFO] No hex file specified, using default: %DEFAULT_HEX%
) else (
    if not exist "%HEX_FILE%" (
        echo [ERROR] File not found: "%HEX_FILE%"
        exit /b 1
    )
    rem Convert to absolute path
    for %%i in ("%HEX_FILE%") do set "HEX_FILE=%%~fi"
)

if not exist "!HEX_FILE!" (
    echo [ERROR] Hex file not found: "!HEX_FILE!"
    echo.
    echo Usage: drag-and-drop a .hex file onto this script, or run:
    echo   %~nx0 ^<path\to\firmware.hex^>
    exit /b 1
)

echo ========================================
echo  STM32 EASY FLASH
echo ========================================
echo  Hex: !HEX_FILE!
echo ========================================
echo.

REM Use bundled OpenOCD only (never system PATH)
if exist "%SCRIPT_DIR%openocd\windows\openocd.exe" (
    set "OPENOCD=%SCRIPT_DIR%openocd\windows\openocd.exe"
    set "SCRIPTS=%SCRIPT_DIR%openocd\windows\scripts"
    if exist "!SCRIPTS!" (
        "!OPENOCD!" -s "!SCRIPTS!" -f interface/stlink.cfg -f target/stm32f1x.cfg -c "program \"!HEX_FILE!\" verify reset exit"
    ) else (
        "!OPENOCD!" -f interface/stlink.cfg -f target/stm32f1x.cfg -c "program \"!HEX_FILE!\" verify reset exit"
    )
) else (
    echo [ERROR] Bundled OpenOCD not found.
    echo         Run the GUI first to auto-download it, or place openocd.exe
    echo         in the openocd\windows\ folder.
    exit /b 1
)

if %ERRORLEVEL% equ 0 (
    echo.
    echo ========================================
    echo  ^> Flash completed successfully!
    echo ========================================
) else (
    echo.
    echo [ERROR] Flash failed! Check ST-Link connection.
    exit /b 1
)

endlocal
