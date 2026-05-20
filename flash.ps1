param(
    [Parameter(Position = 0)]
    [string]$HexFile,

    [switch]$Help
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Resolve-Path "$ScriptDir\.."
$DefaultHex = Join-Path $ProjectDir "build\2026-rov-Float-STM32.hex"
$OpenOcdDir = Join-Path $ScriptDir "openocd\windows"

if ($Help) {
    Write-Host @"
STM32 EASY FLASH (PowerShell)
==============================
Usage:
    .\flash.ps1 [[-HexFile] <path>] [-Help]

Examples:
    .\flash.ps1                          # Flash default hex (build\2026-rov-Float-STM32.hex)
    .\flash.ps1 .\build\firmware.hex     # Flash a specific hex file
    .\flash.ps1 -HexFile "C:\temp\test.hex"

Drag-and-drop: Drag a .hex file onto flash.ps1 in Explorer.
"@ -ForegroundColor Cyan
    return
}

if (-not $HexFile) {
    $HexFile = $DefaultHex
    Write-Host "[INFO] No hex file specified, using default: $HexFile" -ForegroundColor Yellow
}
else {
    $HexFile = Resolve-Path $HexFile -ErrorAction Stop
}

if (-not (Test-Path $HexFile)) {
    Write-Host "[ERROR] Hex file not found: $HexFile" -ForegroundColor Red
    exit 1
}

# Use bundled OpenOCD only — never system PATH
$OpenOcdExe = Join-Path $OpenOcdDir "openocd.exe"
if (-not (Test-Path $OpenOcdExe)) {
    Write-Host "[ERROR] Bundled OpenOCD not found at: $OpenOcdExe" -ForegroundColor Red
    Write-Host "        Run the GUI first to auto-download it, or place openocd.exe" -ForegroundColor Yellow
    Write-Host "        in the openocd\windows\ folder." -ForegroundColor Yellow
    exit 1
}

# Look for scripts directory
$ScriptsDir = Join-Path $OpenOcdDir "scripts"
if (-not (Test-Path $ScriptsDir)) {
    $ScriptsDir = Join-Path $OpenOcdDir "share\openocd\scripts"
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " STM32 EASY FLASH" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Hex: $HexFile" -ForegroundColor White
Write-Host " OpenOCD: $OpenOcdExe (bundled)" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[INFO] Starting flash via OpenOCD (ST-Link)..." -ForegroundColor Green

$openocdArgs = @()
if (Test-Path $ScriptsDir) {
    $openocdArgs += "-s", "`"$ScriptsDir`""
}
$openocdArgs += @(
    "-f", "interface/stlink.cfg",
    "-f", "target/stm32f1x.cfg",
    "-c", "program ""$HexFile"" verify reset exit"
)

Write-Host "       $OpenOcdExe $($openocdArgs -join ' ')" -ForegroundColor DarkGray
Write-Host ""

try {
    $process = Start-Process -FilePath $OpenOcdExe -ArgumentList $openocdArgs -NoNewWindow -Wait -PassThru
    if ($process.ExitCode -eq 0) {
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Cyan
        Write-Host " > Flash completed successfully!" -ForegroundColor Green
        Write-Host "========================================" -ForegroundColor Cyan
    }
    else {
        Write-Host ""
        Write-Host "[ERROR] Flash failed! Exit code: $($process.ExitCode)" -ForegroundColor Red
        Write-Host "        Check ST-Link connection and try again." -ForegroundColor Yellow
        exit $process.ExitCode
    }
}
catch {
    Write-Host "[ERROR] $_" -ForegroundColor Red
    exit 1
}
