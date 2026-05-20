# STM32 EASY FLASH

> All-in-one tool for flashing firmware to **STM32** microcontrollers via **ST-Link**.
>
> **No coding knowledge required. Nothing to install. Completely self-contained.**
>
> Works on **Windows · macOS · Linux**. Never touches system PATH or global environment.

---

## 📋 Quick Start

### 🪟 Windows

| Step | Action |
|------|--------|
| 1 | Double-click **`STM32 EASY FLASH.bat`** |
| 2 | On first launch → auto-downloads OpenOCD (one-time, ~8 MB) |
| 3 | Click **"Browse..."** → select your `.hex` file |
| 4 | Connect ST-Link to the board |
| 5 | Click **"Flash to STM32"** |

### 🍎 macOS / 🐧 Linux

| Step | Action |
|------|--------|
| 1 | Open Terminal in the `easy_flash/` folder |
| 2 | `chmod +x run.sh && ./run.sh` |
| 3 | On first launch → auto-downloads OpenOCD (one-time, ~8 MB) |
| 4 | Click **"Browse..."** → select your `.hex` file |
| 5 | Connect ST-Link to the board |
| 6 | Click **"Flash to STM32"** |

> 💡 **macOS** — may need: `brew install python-tk`
>
> 💡 **Linux** — may need: `sudo apt install python3-tk` (Ubuntu) or `sudo dnf install python3-tkinter` (Fedora)

---

## 📦 What's Inside

```
easy_flash/
│
├── STM32 EASY FLASH.bat   ← Windows:  double-click to launch GUI
├── run.sh                 ← Mac/Linux: ./run.sh to launch GUI
│
├── flash_gui.py           ← Cross-platform GUI  (Python / tkinter)
├── flash.py               ← Cross-platform CLI  (Python)
│
├── flash_gui.ps1          ← Windows PowerShell GUI  (legacy fallback)
├── flash.bat              ← Windows CLI  (legacy fallback)
├── flash.ps1              ← Windows PowerShell CLI (legacy fallback)
│
├── README.md              ← This file
│
└── openocd/               ← ⏳ Auto-created on first launch
    ├── windows/            ← Windows: openocd.exe + DLLs + scripts/
    ├── macos/              ← macOS:   openocd + .dylib + scripts/
    └── linux/              ← Linux:   openocd + .so + scripts/
```

---

## ✅ What You Need

| Item | Notes |
|------|-------|
| **This `easy_flash/` folder** | Everything is inside here — nothing installed elsewhere |
| **Python 3.6+** (any OS) | <https://www.python.org/downloads/> |
| **Internet (first run only)** | Auto-downloads OpenOCD into `openocd/` folder |
| **A `.hex` firmware file** | From your build (e.g. `build/2026-rov-Float-STM32.hex`) |
| **ST-Link programmer** | Connected to your board via USB |

---

## 🔌 ST-Link Driver

The ST-Link programmer needs a driver to talk to OpenOCD.

> ⚠️ **First time plugging in ST-Link?** Your OS handles the driver:
>
> - **Windows** — auto-installs on first connection. Wait for "Device ready" notification.
> - **macOS / Linux** — works natively (driver built into the OS).

| OS | Normal | If it doesn't work |
|-----|--------|-------------------|
| **Windows** | Plug & play — auto-installed | Use [Zadig](https://zadig.akeo.ie/) → select ST-Link → install **WinUSB** |
| **macOS** | Works out of the box | `brew install libusb` |
| **Linux** | Built into kernel | `sudo apt install libusb-1.0-0-dev` (Ubuntu/Debian) |

> 🐧 **WSL / Linux — missing library errors?**  
> If you see `error while loading shared libraries` when flashing, install the missing packages:
>
> ```bash
> sudo apt update
> sudo apt install libftdi1-2 libhidapi-hidraw0 libusb-1.0-0
> ```
>
> The error will tell you exactly which `.so` file is missing — just `apt install` the corresponding package.

---

## 🔒 Safety Guarantees

| Your system... | What we do |
|---------------|------------|
| **System PATH** | 🚫 Never touched |
| **Registry / dotfiles** | 🚫 Never touched |
| **Admin / root rights** | 🚫 Never required |
| **Global installs** | 🚫 Never performed |
| **OpenOCD location** | ✅ Only ever from `easy_flash/openocd/` |
| **Working directory** | ✅ Always runs from `easy_flash/` folder |

---

## ❓ Manual OpenOCD Install

If the auto-download fails, you can do it by hand:

1. Download the **xPack OpenOCD** build for **your OS**:  
   <https://github.com/xpack-dev-tools/openocd-xpack/releases>

2. Extract the archive

3. Copy files into `easy_flash/openocd/`:

   ```
   From the zip/tar.gz                     →  easy_flash/openocd/<os>/
   ─────────────────────────────────────────────────────────────────
   Windows: bin/openocd.exe + bin/*.dll     →  openocd/windows/
   Windows: openocd/scripts/                →  openocd/windows/scripts/

   macOS:   bin/openocd + bin/*.dylib       →  openocd/macos/
   macOS:   openocd/scripts/                →  openocd/macos/scripts/

   Linux:   bin/openocd + bin/*.so          →  openocd/linux/
   Linux:   openocd/scripts/                →  openocd/linux/scripts/
   ```

---

## ⚡ CLI for Developers

No GUI needed? Use the Python CLI directly.

### Any OS

```bash
# Flash the default hex file
python flash.py

# Flash a specific hex file
python flash.py ../build/my-firmware.hex

# Custom interface/target configs
python flash.py firmware.hex --interface interface/jlink.cfg --target target/stm32f4x.cfg
```

### Per-platform launchers (fallback, no Python needed)

```bash
# Windows
flash.bat build\2026-rov-Float-STM32.hex

# macOS / Linux
./run.sh --cli ../build/2026-rov-Float-STM32.hex
```

---

## 📝 Notes

- OpenOCD auto-downloads once on first launch (stays inside `openocd/` folder).
- ST-Link v2 (or v3) programmer must be connected via USB.
- After flashing, the MCU is verified and reset automatically.
- Drag-and-drop a `.hex` file onto the GUI window for quick loading.
