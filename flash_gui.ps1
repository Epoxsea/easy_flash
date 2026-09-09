<#
.SYNOPSIS
    STM32 EASY FLASH GUI - All-in-one firmware flasher for STM32 via ST-Link.
    No coding knowledge required. No extra software needed to install.
.DESCRIPTION
    Self-contained GUI application that bundles/handles everything needed
    to flash firmware to STM32 microcontrollers using OpenOCD and ST-Link.
    Automatically downloads OpenOCD if not found on the system.
#>

#requires -Version 5.1

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.IO.Compression.FileSystem

# =========================================================
# Configuration
# =========================================================
$Script:ProjectRoot = Resolve-Path "$PSScriptRoot\.."
$Script:DefaultHex = ""
$Script:OpenOcdDir = Join-Path $PSScriptRoot "openocd\windows"
$Script:IsFlashing = $false

# OpenOCD download info - dynamically resolved from GitHub API
$Script:OpenOcdArchive = Join-Path $PSScriptRoot "openocd.zip"
$Script:OpenOcdExe = Join-Path $Script:OpenOcdDir "openocd.exe"
$Script:OpenOcdApiUrl = ""

# Default config files (relative paths for bundled OpenOCD's -s dir)
$Script:DefaultInterfaceCfg = "interface/stlink.cfg"
$Script:DefaultTargetCfg = "target/stm32f1x.cfg"

# =========================================================
# Helper Functions
# =========================================================

function Write-Log {
    param([string]$Text, [string]$Color = "Black")
    if ($Script:OutputBox) {
        $Script:OutputBox.SelectionStart = $Script:OutputBox.TextLength
        $Script:OutputBox.SelectionLength = 0
        $Script:OutputBox.SelectionColor = $Color
        $Script:OutputBox.AppendText($Text + "`r`n")
        $Script:OutputBox.ScrollToCaret()
    }
}

function Update-Status {
    param([string]$Text, [string]$Color = "Black")
    if ($Script:StatusLabel) {
        $Script:StatusLabel.Text = $Text
        $Script:StatusLabel.ForeColor = $Color
    }
}

function Test-OpenOcd {
    # Only use bundled OpenOCD - never system
    return (Test-Path $Script:OpenOcdExe)
}

function Get-OpenOcdPath {
    # Only use bundled OpenOCD - never system
    if (Test-Path $Script:OpenOcdExe) { return $Script:OpenOcdExe }
    return $null
}

function Invoke-Flash {
    param([string]$HexPath)

    if ($Script:IsFlashing) { return }

    if (-not (Test-Path $HexPath)) {
        [System.Windows.Forms.MessageBox]::Show(
            "Hex file not found:`n$HexPath",
            "File Not Found",
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Error
        )
        return
    }

    $openocd = Get-OpenOcdPath
    if (-not $openocd) {
        [System.Windows.Forms.MessageBox]::Show(
            "OpenOCD is not available. Please install it or use the 'Install OpenOCD' button.",
            "OpenOCD Missing",
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Warning
        )
        return
    }

    $Script:IsFlashing = $true
    $FlashBtn.Enabled = $false
    $BrowseHexBtn.Enabled = $false
    $BrowseIntBtn.Enabled = $false
    $BrowseTgtBtn.Enabled = $false
    $Script:OutputBox.Clear()

    Write-Log "========================================" "Blue"
    Write-Log " STM32 EASY FLASH" "Blue"
    Write-Log "========================================" "Blue"
    Write-Log " Hex: $HexPath" "DarkCyan"
    Write-Log " OpenOCD: $openocd" "DarkCyan"
    Write-Log " (bundled)" "DarkCyan"
    Write-Log "========================================" "Blue"
    Write-Log ""

    Write-Log "[INFO] Starting flash via ST-Link..." "Green"

    # Determine scripts dir for bundled OpenOCD
    $scriptDir = $null
    if ($openocd -ne "openocd") {
        $openocdBase = Split-Path $openocd -Parent
        # xPack structure: openocd_dir/scripts/
        $scriptDir = Join-Path $openocdBase "scripts"
        if (-not (Test-Path $scriptDir)) {
            # Standard structure: openocd_dir/share/openocd/scripts/
            $scriptDir = Join-Path $openocdBase "share\openocd\scripts"
        }
    }

    # Build arguments
    # Note: -c value needs quotes to stay as one arg (no shell with UseShellExecute=$false)
    $HexPathSafe = $HexPath -replace '\\', '/'  # forward slashes avoid TCL escape issues
    $tclCmd = "program $HexPathSafe verify reset exit"
    $openocdArgs = @()
    if ($scriptDir -and (Test-Path $scriptDir)) {
        $openocdArgs += "-s", $scriptDir
        Write-Log "[INFO] Scripts dir: $scriptDir" "DarkCyan"
    }
    # Use selected cfg files (or defaults)
    $cfgInterface = $Script:InterfaceCfgPath
    $cfgTarget = $Script:TargetCfgPath
    if (-not $cfgInterface) { $cfgInterface = $Script:DefaultInterfaceCfg }
    if (-not $cfgTarget) { $cfgTarget = $Script:DefaultTargetCfg }
    $openocdArgs += "-f", "`"$cfgInterface`"", "-f", "`"$cfgTarget`"", "-c", "`"$tclCmd`""

    Write-Log "       $openocd $($openocdArgs -join ' ')" "Gray"
    Write-Log ""

    try {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $openocd
        $psi.Arguments = $openocdArgs
        $psi.UseShellExecute = $false
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.CreateNoWindow = $true
        # Always use the project root as working directory (same as command line)
        $psi.WorkingDirectory = $Script:ProjectRoot

        $proc = New-Object System.Diagnostics.Process
        $proc.StartInfo = $psi

        $proc.Start() | Out-Null

        # Read output line by line (synchronous but keeps UI responsive via DoEvents)
        $allOut = New-Object System.Text.StringBuilder
        do {
            $line = $proc.StandardOutput.ReadLine()
            if ($line) { Write-Log $line "DarkGray"; $null = $allOut.AppendLine($line) }
            $errLine = $proc.StandardError.ReadLine()
            if ($errLine) { Write-Log $errLine "DarkGray"; $null = $allOut.AppendLine($errLine) }
            [System.Windows.Forms.Application]::DoEvents()
            Start-Sleep -Milliseconds 20
        } while (-not $proc.HasExited)

        # Drain any remaining output
        while ($null -ne ($line = $proc.StandardOutput.ReadLine())) {
            Write-Log $line "DarkGray"; $null = $allOut.AppendLine($line)
        }
        while ($null -ne ($line = $proc.StandardError.ReadLine())) {
            Write-Log $line "DarkGray"; $null = $allOut.AppendLine($line)
        }

        $proc.WaitForExit()

        Write-Log ""
        if ($proc.ExitCode -eq 0) {
            Write-Log "========================================" "Green"
            Write-Log " >>> Flash completed successfully! <<<" "Green"
            Write-Log "========================================" "Green"
            Update-Status "Ready - Last flash: SUCCESS" "Green"
            $FlashBtn.BackColor = [System.Drawing.Color]::LightGreen
        }
        else {
            Write-Log "========================================" "Red"
            Write-Log " >>> Flash FAILED! (exit code: $($proc.ExitCode)) <<<" "Red"
            Write-Log "========================================" "Red"
            Update-Status "Ready - Last flash: FAILED" "Red"
        }
    }
    catch {
        Write-Log "[ERROR] $_" "Red"
        Update-Status "Error - $_" "Red"
    }
    finally {
        $Script:IsFlashing = $false
        $FlashBtn.Enabled = $true
        $BrowseHexBtn.Enabled = $true
        $BrowseIntBtn.Enabled = $true
        $BrowseTgtBtn.Enabled = $true
        Get-EventSubscriber | Unregister-Event -Force -ErrorAction SilentlyContinue
    }
}

function Get-LatestOpenOcdUrl {
    <#
    .SYNOPSIS
        Returns a known-working OpenOCD download URL for Windows.
        Uses the xPack build (self-contained, no extra DLLs needed).
    #>
    Write-Log "[INFO] OpenOCD download URL: xPack build (self-contained)" "DarkCyan"
    # xPack OpenOCD v0.12.0-7 - self-contained Windows 64-bit build
    return "https://github.com/xpack-dev-tools/openocd-xpack/releases/download/v0.12.0-7/xpack-openocd-0.12.0-7-win32-x64.zip"
}

function Install-BundledOpenOcd {
    $InstallBtn.Enabled = $false
    $Script:OutputBox.Clear()

    Write-Log "========================================" "Blue"
    Write-Log " Installing OpenOCD (bundled)..." "Blue"
    Write-Log "========================================" "Blue"
    Write-Log ""

    try {
        # Step 1: Get download URL
        $downloadUrl = Get-LatestOpenOcdUrl

        # Create openocd directory (clean)
        if (Test-Path $Script:OpenOcdDir) {
            Remove-Item $Script:OpenOcdDir -Recurse -Force
        }
        New-Item -ItemType Directory -Path $Script:OpenOcdDir -Force | Out-Null

        # Step 2: Download
        Write-Log "[INFO] Downloading OpenOCD..." "Green"
        Write-Log "       $downloadUrl" "DarkCyan"
        Update-Status "Downloading OpenOCD..." "Orange"

        $downloader = [System.Net.WebClient]::new()
        Register-ObjectEvent -InputObject $downloader -EventName DownloadProgressChanged -Action {
            $percent = $event.SourceEventArgs.ProgressPercentage
            Write-Progress -Activity "Downloading OpenOCD" -Status "$percent%" -PercentComplete $percent
        } | Out-Null

        $downloader.DownloadFile($downloadUrl, $Script:OpenOcdArchive)
        Write-Progress -Activity "Downloading OpenOCD" -Completed
        Write-Log "[INFO] Download complete!" "Green"

        # Step 3: Extract using built-in zip support
        Write-Log "[INFO] Extracting (this may take a moment)..." "Green"
        Update-Status "Extracting OpenOCD..." "Orange"

        $extractTemp = Join-Path $PSScriptRoot "openocd_temp"
        if (Test-Path $extractTemp) { Remove-Item $extractTemp -Recurse -Force }
        New-Item -ItemType Directory -Path $extractTemp -Force | Out-Null

        # Extract zip
        [System.IO.Compression.ZipFile]::ExtractToDirectory($Script:OpenOcdArchive, $extractTemp)
        Write-Log "[OK] Extraction complete" "DarkGreen"

        # Step 4: Find the xPack folder and move contents up
        $extractedRoot = Get-ChildItem -Path $extractTemp -Directory | Select-Object -First 1
        if (-not $extractedRoot) { $extractedRoot = $extractTemp }

        # The xPack build has a nested structure:
        #   xpack-openocd-x.x.x-x/
        #     bin/           -> openocd.exe + DLLs
        #     openocd/scripts/ -> interface/stlink.cfg, target/stm32f1x.cfg, etc.

        # Find the top-level folder that contains openocd.exe
        $exeDir = Get-ChildItem -Path $extractedRoot.FullName -Recurse -Filter "openocd.exe" |
        Select-Object -First 1 | ForEach-Object { $_.DirectoryName }
        if (-not $exeDir) { throw "openocd.exe not found in extracted archive" }

        # The root of the xPack package (parent of bin/)
        $xpackRoot = Split-Path $exeDir -Parent

        # Copy bin/ contents (openocd.exe + all DLLs)
        Copy-Item "$exeDir\*" $Script:OpenOcdDir -Recurse -Force
        Write-Log "[OK] openocd.exe + DLLs copied" "DarkGreen"

        # Copy openocd/scripts/ (xPack puts them directly under the root, not share/!)
        $scriptsSource = Join-Path $xpackRoot "openocd\scripts"
        if (Test-Path $scriptsSource) {
            $targetScripts = Join-Path $Script:OpenOcdDir "scripts"
            Copy-Item $scriptsSource $targetScripts -Recurse -Force
            Write-Log "[OK] Scripts copied (interface/, target/, etc.)" "DarkGreen"
        }
        else {
            Write-Log "[WARN] Scripts not found at $scriptsSource" "Orange"
        }

        Write-Log "[OK] Files installed (self-contained build)" "DarkGreen"

        # Cleanup temp & archive
        Remove-Item $extractTemp -Recurse -Force -ErrorAction SilentlyContinue
        Remove-Item $Script:OpenOcdArchive -Force -ErrorAction SilentlyContinue

        # Verify key files exist
        $testExe = Join-Path $Script:OpenOcdDir "openocd.exe"
        if (Test-Path $testExe) {
            Write-Log ""
            Write-Log "========================================" "Green"
            Write-Log " OpenOCD installed successfully!" "Green"
            Write-Log "========================================" "Green"
            Write-Log ""
            Write-Log "  location: $Script:OpenOcdDir" "DarkGreen"
            Update-Status "Ready (bundled OpenOCD)" "Green"
        }
        else {
            Write-Log "[WARN] openocd.exe not found after extraction" "Orange"
        }
    }
    catch {
        Write-Log "[ERROR] Download/install failed: $_" "Red"
        Write-Log "[HINT] You can manually download OpenOCD (xPack build) from:" "Orange"
        Write-Log "       https://github.com/xpack-dev-tools/openocd-xpack/releases" "Orange"
        Write-Log "[HINT] Extract the zip, then copy:" "Orange"
        Write-Log "         bin/*          -> $Script:OpenOcdDir\" "Orange"
        Write-Log "         openocd/scripts/ -> $Script:OpenOcdDir\scripts\" "Orange"
    }
    finally {
        # Cleanup any leftover temp files
        $temp = Join-Path $PSScriptRoot "openocd_temp"
        if (Test-Path $temp) { Remove-Item $temp -Recurse -Force -ErrorAction SilentlyContinue }
        Remove-Item $Script:OpenOcdArchive -Force -ErrorAction SilentlyContinue
        $InstallBtn.Enabled = $true
        Get-EventSubscriber | Unregister-Event -Force -ErrorAction SilentlyContinue
    }
}

# =========================================================
# Build the GUI
# =========================================================

# Main form
$Form = New-Object System.Windows.Forms.Form
$Form.Text = "STM32 EASY FLASH"
$Form.ClientSize = New-Object System.Drawing.Size(775, 635)
$Form.MinimumSize = $Form.ClientSize
$Form.MaximumSize = $Form.ClientSize
$Form.FormBorderStyle = "FixedSingle"
$Form.MaximizeBox = $false
$Form.StartPosition = "CenterScreen"
$Form.Font = New-Object System.Drawing.Font("Segoe UI", 9.5)
$Form.BackColor = [System.Drawing.Color]::White

# Title bar
$TitleBar = New-Object System.Windows.Forms.Panel
$TitleBar.Size = New-Object System.Drawing.Size(760, 60)
$TitleBar.BackColor = [System.Drawing.Color]::FromArgb(0, 103, 192)
$TitleBar.Dock = "Top"

$TitleIcon = New-Object System.Windows.Forms.Label
$TitleIcon.Text = "STM32"
$TitleIcon.Font = New-Object System.Drawing.Font("Segoe UI", 18, [System.Drawing.FontStyle]::Bold)
$TitleIcon.ForeColor = [System.Drawing.Color]::White
$TitleIcon.Location = New-Object System.Drawing.Point(8, 4)
$TitleIcon.Size = New-Object System.Drawing.Size(92, 30)

$TitleText = New-Object System.Windows.Forms.Label
$TitleText.Text = "EASY FLASH"
$TitleText.Font = New-Object System.Drawing.Font("Segoe UI", 13)
$TitleText.ForeColor = [System.Drawing.Color]::FromArgb(180, 210, 255)
$TitleText.Location = New-Object System.Drawing.Point(104, 7)
$TitleText.Size = New-Object System.Drawing.Size(115, 22)

$TitleSub = New-Object System.Windows.Forms.Label
$TitleSub.Text = "ST-Link Firmware Flasher  |  No coding, no setup, just flash!"
$TitleSub.Font = New-Object System.Drawing.Font("Segoe UI", 8.5)
$TitleSub.ForeColor = [System.Drawing.Color]::FromArgb(200, 220, 255)
$TitleSub.Location = New-Object System.Drawing.Point(8, 32)
$TitleSub.Size = New-Object System.Drawing.Size(500, 18)

$TitleBar.Controls.AddRange(@($TitleIcon, $TitleText, $TitleSub))

# Main panel
$MainPanel = New-Object System.Windows.Forms.Panel
$MainPanel.Dock = "Fill"

# --- Firmware file ---
$FileGroup = New-Object System.Windows.Forms.GroupBox
$FileGroup.Text = "Firmware File (.hex)"
$FileGroup.Location = New-Object System.Drawing.Point(12, 68)
$FileGroup.Size = New-Object System.Drawing.Size(736, 50)

$HexPathBox = New-Object System.Windows.Forms.TextBox
$HexPathBox.Location = New-Object System.Drawing.Point(12, 20)
$HexPathBox.Size = New-Object System.Drawing.Size(560, 22)
$HexPathBox.Text = "Select a .hex file or drag it here..."
$HexPathBox.ForeColor = [System.Drawing.Color]::Gray

$BrowseHexBtn = New-Object System.Windows.Forms.Button
$BrowseHexBtn.Text = "Browse..."
$BrowseHexBtn.Location = New-Object System.Drawing.Point(580, 18)
$BrowseHexBtn.Size = New-Object System.Drawing.Size(140, 26)
$BrowseHexBtn.UseVisualStyleBackColor = $true
$BrowseHexBtn.Add_Click({
        $ofd = New-Object System.Windows.Forms.OpenFileDialog
        $ofd.Filter = "Hex files (*.hex)|*.hex|All files (*.*)|*.*"
        $ofd.Title = "Select firmware hex file"
        #use the 
        $buildDir = Join-Path $Script:ProjectRoot "build"
        if (Test-Path $buildDir) { $ofd.InitialDirectory = $buildDir }
        if ($ofd.ShowDialog($Form) -eq [System.Windows.Forms.DialogResult]::OK) {
            $HexPathBox.Text = $ofd.FileName
            $HexPathBox.ForeColor = [System.Drawing.Color]::Black
        }
    })
$FileGroup.Controls.AddRange(@($HexPathBox, $BrowseHexBtn))

# --- Config files ---
$CfgGroup = New-Object System.Windows.Forms.GroupBox
$CfgGroup.Text = "OpenOCD Config Files"
$CfgGroup.Location = New-Object System.Drawing.Point(12, 120)
$CfgGroup.Size = New-Object System.Drawing.Size(736, 72)

# Interface cfg
$IntCfgLabel = New-Object System.Windows.Forms.Label
$IntCfgLabel.Text = "Interface:"
$IntCfgLabel.Location = New-Object System.Drawing.Point(10, 18)
$IntCfgLabel.Size = New-Object System.Drawing.Size(60, 18)

$Script:InterfaceCfgPath = $Script:DefaultInterfaceCfg
$IntCfgBox = New-Object System.Windows.Forms.TextBox
$IntCfgBox.Text = $Script:InterfaceCfgPath
$IntCfgBox.Location = New-Object System.Drawing.Point(72, 18)
$IntCfgBox.Size = New-Object System.Drawing.Size(400, 22)
$IntCfgBox.Add_TextChanged({ $Script:InterfaceCfgPath = $IntCfgBox.Text })

$BrowseIntBtn = New-Object System.Windows.Forms.Button
$BrowseIntBtn.Text = "Browse..."
$BrowseIntBtn.Location = New-Object System.Drawing.Point(480, 16)
$BrowseIntBtn.Size = New-Object System.Drawing.Size(110, 24)
$BrowseIntBtn.UseVisualStyleBackColor = $true
$BrowseIntBtn.Add_Click({
        $ofd = New-Object System.Windows.Forms.OpenFileDialog
        $ofd.Filter = "Config files (*.cfg)|*.cfg|All files (*.*)|*.*"
        $ofd.Title = "Select interface config file"
        if ($ofd.ShowDialog($Form) -eq [System.Windows.Forms.DialogResult]::OK) {
            $IntCfgBox.Text = $ofd.FileName
            $Script:InterfaceCfgPath = $ofd.FileName
        }
    })
$ResetIntBtn = New-Object System.Windows.Forms.LinkLabel
$ResetIntBtn.Text = "reset"
$ResetIntBtn.Location = New-Object System.Drawing.Point(598, 14)
$ResetIntBtn.Size = New-Object System.Drawing.Size(60, 18)
$ResetIntBtn.LinkColor = [System.Drawing.Color]::Gray
$ResetIntBtn.Add_Click({ $IntCfgBox.Text = $Script:DefaultInterfaceCfg; $Script:InterfaceCfgPath = $Script:DefaultInterfaceCfg })

# Target cfg
$TgtCfgLabel = New-Object System.Windows.Forms.Label
$TgtCfgLabel.Text = "Target:"
$TgtCfgLabel.Location = New-Object System.Drawing.Point(10, 44)
$TgtCfgLabel.Size = New-Object System.Drawing.Size(60, 18)

$Script:TargetCfgPath = $Script:DefaultTargetCfg
$TgtCfgBox = New-Object System.Windows.Forms.TextBox
$TgtCfgBox.Text = $Script:TargetCfgPath
$TgtCfgBox.Location = New-Object System.Drawing.Point(72, 42)
$TgtCfgBox.Size = New-Object System.Drawing.Size(400, 22)
$TgtCfgBox.Add_TextChanged({ $Script:TargetCfgPath = $TgtCfgBox.Text })

$BrowseTgtBtn = New-Object System.Windows.Forms.Button
$BrowseTgtBtn.Text = "Browse..."
$BrowseTgtBtn.Location = New-Object System.Drawing.Point(480, 40)
$BrowseTgtBtn.Size = New-Object System.Drawing.Size(110, 24)
$BrowseTgtBtn.UseVisualStyleBackColor = $true
$BrowseTgtBtn.Add_Click({
        $ofd = New-Object System.Windows.Forms.OpenFileDialog
        $ofd.Filter = "Config files (*.cfg)|*.cfg|All files (*.*)|*.*"
        $ofd.Title = "Select target config file"
        if ($ofd.ShowDialog($Form) -eq [System.Windows.Forms.DialogResult]::OK) {
            $TgtCfgBox.Text = $ofd.FileName
            $Script:TargetCfgPath = $ofd.FileName
        }
    })
$ResetTgtBtn = New-Object System.Windows.Forms.LinkLabel
$ResetTgtBtn.Text = "reset"
$ResetTgtBtn.Location = New-Object System.Drawing.Point(598, 42)
$ResetTgtBtn.Size = New-Object System.Drawing.Size(60, 18)
$ResetTgtBtn.LinkColor = [System.Drawing.Color]::Gray
$ResetTgtBtn.Add_Click({ $TgtCfgBox.Text = $Script:DefaultTargetCfg; $Script:TargetCfgPath = $Script:DefaultTargetCfg })

$CfgGroup.Controls.AddRange(@($IntCfgLabel, $IntCfgBox, $BrowseIntBtn, $ResetIntBtn,
        $TgtCfgLabel, $TgtCfgBox, $BrowseTgtBtn, $ResetTgtBtn))

# --- Action buttons ---
$FlashBtn = New-Object System.Windows.Forms.Button
$FlashBtn.Text = ">  Flash to STM32"
$FlashBtn.Location = New-Object System.Drawing.Point(12, 200)
$FlashBtn.Size = New-Object System.Drawing.Size(375, 38)
$FlashBtn.Font = New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)
$FlashBtn.BackColor = [System.Drawing.Color]::FromArgb(0, 120, 215)
$FlashBtn.ForeColor = [System.Drawing.Color]::White
$FlashBtn.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$FlashBtn.FlatAppearance.BorderSize = 0
$FlashBtn.Cursor = [System.Windows.Forms.Cursors]::Hand
$FlashBtn.Add_Click({
        if (-not $Script:IsFlashing) {
            $path = $HexPathBox.Text
            if (Test-Path $path) {
                Invoke-Flash -HexPath $path
            }
            else {
                [System.Windows.Forms.MessageBox]::Show($Form,
                    "Please select a valid .hex file first.",
                    "No File Selected",
                    [System.Windows.Forms.MessageBoxButtons]::OK,
                    [System.Windows.Forms.MessageBoxIcon]::Information)
            }
        }
    })
$FlashBtn.Add_MouseEnter({ if ($FlashBtn.Enabled) { $FlashBtn.BackColor = [System.Drawing.Color]::FromArgb(0, 140, 235) } })
$FlashBtn.Add_MouseLeave({ if ($FlashBtn.Enabled) { $FlashBtn.BackColor = [System.Drawing.Color]::FromArgb(0, 120, 215) } })

$InstallBtn = New-Object System.Windows.Forms.Button
$InstallBtn.Text = "Install OpenOCD"
$InstallBtn.Location = New-Object System.Drawing.Point(395, 200)
$InstallBtn.Size = New-Object System.Drawing.Size(353, 38)
$InstallBtn.Font = New-Object System.Drawing.Font("Segoe UI", 9.5)
$InstallBtn.BackColor = [System.Drawing.Color]::FromArgb(80, 80, 80)
$InstallBtn.ForeColor = [System.Drawing.Color]::White
$InstallBtn.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$InstallBtn.FlatAppearance.BorderSize = 0
$InstallBtn.Cursor = [System.Windows.Forms.Cursors]::Hand
$InstallBtn.Add_Click({ Install-BundledOpenOcd })
$InstallBtn.Add_MouseEnter({ $InstallBtn.BackColor = [System.Drawing.Color]::FromArgb(100, 100, 100) })
$InstallBtn.Add_MouseLeave({ $InstallBtn.BackColor = [System.Drawing.Color]::FromArgb(80, 80, 80) })

# --- Output section ---
$OutputGroup = New-Object System.Windows.Forms.GroupBox
$OutputGroup.Text = "Output Log"
$OutputGroup.Location = New-Object System.Drawing.Point(12, 244)
$OutputGroup.Size = New-Object System.Drawing.Size(736, 310)

$Script:OutputBox = New-Object System.Windows.Forms.RichTextBox
$Script:OutputBox.Location = New-Object System.Drawing.Point(10, 18)
$Script:OutputBox.Size = New-Object System.Drawing.Size(716, 282)
$Script:OutputBox.ReadOnly = $true
$Script:OutputBox.BackColor = [System.Drawing.Color]::FromArgb(30, 30, 30)
$Script:OutputBox.ForeColor = [System.Drawing.Color]::LightGray
$Script:OutputBox.Font = New-Object System.Drawing.Font("Consolas", 9.5)
$Script:OutputBox.BorderStyle = [System.Windows.Forms.BorderStyle]::FixedSingle
$Script:OutputBox.WordWrap = $false
$Script:OutputBox.Text = "Welcome to STM32 EASY FLASH!`r`n`r`n"
$Script:OutputBox.AppendText("Instructions:`r`n")
$Script:OutputBox.AppendText("  1. Click 'Browse...' to select a .hex file`r`n")
$Script:OutputBox.AppendText("  2. Connect ST-Link to your board`r`n")
$Script:OutputBox.AppendText("  3. Click 'Flash to STM32'`r`n")
$Script:OutputBox.AppendText("`r`n")
$Script:OutputBox.AppendText("You can also drag-and-drop a .hex file onto this window.`r`n")

# Drag-and-drop
$Script:OutputBox.AllowDrop = $true
$Form.AllowDrop = $true
$Script:OutputBox.Add_DragEnter({ if ($_.Data.GetDataPresent([System.Windows.Forms.DataFormats]::FileDrop)) { $_.Effect = [System.Windows.Forms.DragDropEffects]::Copy } })
$Form.Add_DragEnter({ if ($_.Data.GetDataPresent([System.Windows.Forms.DataFormats]::FileDrop)) { $_.Effect = [System.Windows.Forms.DragDropEffects]::Copy } })
$Script:OutputBox.Add_DragDrop({
        $files = $_.Data.GetData([System.Windows.Forms.DataFormats]::FileDrop)
        if ($files -and $files.Count -gt 0) {
            $file = $files[0]
            if ($file -like "*.hex") {
                $HexPathBox.Text = $file
                $HexPathBox.ForeColor = [System.Drawing.Color]::Black
                Write-Log "[INFO] Loaded: $file" "DarkCyan"
                $result = [System.Windows.Forms.MessageBox]::Show($Form,
                    "Flash this file now?", "Auto-Flash",
                    [System.Windows.Forms.MessageBoxButtons]::YesNo,
                    [System.Windows.Forms.MessageBoxIcon]::Question)
                if ($result -eq "Yes") { Invoke-Flash -HexPath $file }
            }
            else {
                Write-Log "[WARNING] Please drop a .hex file (got: $file)" "Orange"
            }
        }
    })
$Form.Add_DragDrop({
        $files = $_.Data.GetData([System.Windows.Forms.DataFormats]::FileDrop)
        if ($files -and $files.Count -gt 0) {
            $file = $files[0]
            if ($file -like "*.hex") {
                $HexPathBox.Text = $file
                $HexPathBox.ForeColor = [System.Drawing.Color]::Black
                Write-Log "[INFO] Loaded: $file" "DarkCyan"
            }
        }
    })
$OutputGroup.Controls.Add($Script:OutputBox)

# --- Status bar ---
$StatusPanel = New-Object System.Windows.Forms.Panel
$StatusPanel.Height = 28
$StatusPanel.Dock = "Bottom"
$StatusPanel.BackColor = [System.Drawing.Color]::FromArgb(240, 240, 240)

$Script:StatusLabel = New-Object System.Windows.Forms.Label
$Script:StatusLabel.Text = "Initializing..."
$Script:StatusLabel.Location = New-Object System.Drawing.Point(12, 5)
$Script:StatusLabel.Size = New-Object System.Drawing.Size(500, 18)
$Script:StatusLabel.ForeColor = [System.Drawing.Color]::Gray
$StatusPanel.Controls.Add($Script:StatusLabel)

$VersionLabel = New-Object System.Windows.Forms.Label
$VersionLabel.Text = "v1.0"
$VersionLabel.Location = New-Object System.Drawing.Point(700, 5)
$VersionLabel.Size = New-Object System.Drawing.Size(50, 18)
$VersionLabel.ForeColor = [System.Drawing.Color]::Gray
$VersionLabel.TextAlign = "MiddleRight"
$StatusPanel.Controls.Add($VersionLabel)

# Assemble main panel
$MainPanel.Controls.AddRange(@($FileGroup, $CfgGroup, $FlashBtn, $InstallBtn, $OutputGroup))

# Assemble form
$Form.Controls.AddRange(@($TitleBar, $MainPanel, $StatusPanel))

# =========================================================
# Start-up checks
# =========================================================

# Check OpenOCD on load
$Form.Add_Shown({
        $Form.Activate()

        if (Test-OpenOcd) {
            Update-Status "Ready (bundled OpenOCD)" "Green"
            Write-Log "[OK] Using bundled OpenOCD" "DarkGreen"
        }
        else {
            Write-Log "[INFO] OpenOCD not found. Auto-downloading..." "Orange"
            Write-Log "[INFO] This is a one-time setup." "Orange"
            $InstallBtn.Enabled = $false
            Install-BundledOpenOcd
            if (-not (Test-OpenOcd)) {
                Write-Log ""
                Write-Log "[HINT] If download fails, manually install:" "Orange"
                Write-Log "       Download: https://github.com/xpack-dev-tools/openocd-xpack/releases" "Orange"
                Write-Log "       Extract zip, copy into: $Script:OpenOcdDir" "Orange"
                Write-Log "       Make sure 'openocd.exe' and 'scripts/' folder exist." "Orange"
                Write-Log ""
                Update-Status "OpenOCD download failed - see log for manual steps" "Red"
            }
        }

        # Also check if default hex exists
        if ($Script:DefaultHex -and (Test-Path $Script:DefaultHex)) {
            Write-Log "[OK] Default hex found: $($Script:DefaultHex)" "DarkGreen"
        }
        else {
            Write-Log "[INFO] No default hex file. Select one via Browse or drag-and-drop." "Gray"
        }
    })

# =========================================================
# Launch
# =========================================================
[System.Windows.Forms.Application]::Run($Form)
