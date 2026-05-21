<p align="center">
  <img src="https://img.shields.io/badge/platform-Windows%20|%20macOS%20|%20Linux-blue?style=flat-square" alt="Platform">
  <img src="https://img.shields.io/badge/python-3.6+-brightgreen?style=flat-square" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-yellow?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/status-beta-orange?style=flat-square" alt="Status">
</p>

# STM32 EASY FLASH

> **Zeroconf firmware flasher for STM32 via ST-Link.**  
> One click. No setup. No PATH pollution. Works on every OS.

Drag a `.hex` file, click **Flash**, done. Everything is self-contained inside the `easy_flash/` folder — nothing touches your system.

---

## 🧠 Motivation

I work in a robotics team with people from all backgrounds — hardware, mechanical, electrical, and software. Flashing firmware onto an STM32 board should not require understanding OpenOCD, drivers, or terminal commands.

Existing tools like STM32 Programmer are powerful but clunky and intimidating for non-developers. This project exists so **anyone on the team** can grab a `.hex` file, plug in an ST-Link, and flash in seconds — no explanations needed.

---

## 🚀 Quick Start

### 🪟 Windows

| Step | Action |
|------|--------|
| 1 | Double-click **`STM32 EASY FLASH.bat`** |
| 2 | Auto-downloads OpenOCD on first run (one-time, ~8 MB) |
| 3 | Click **Browse...** → select your `.hex` file |
| 4 | Connect ST-Link to the board |
| 5 | Click **Flash to STM32** ✅ |

### 🍎 macOS / 🐧 Linux

> **⚠️ Note for Mac/Linux users:** This version requires **Python 3** and the **tkinter** library.
> See the tips below the table for install commands.

| Step | Action |
|------|--------|
| 1 | Open Terminal in the `easy_flash/` folder |
| 2 | `chmod +x run.sh && ./run.sh` |
| 3 | Auto-downloads OpenOCD on first run (one-time, ~8 MB) |
| 4 | Click **Browse...** → select your `.hex` file |
| 5 | Connect ST-Link to the board |
| 6 | Click **Flash to STM32** ✅ |

> 💡 **macOS** — may need: `brew install python-tk`  
> 💡 **Linux** — may need: `sudo apt install python3-tk` (Ubuntu) / `sudo dnf install python3-tkinter` (Fedora)

---

## 📂 Project Structure

```
easy_flash/
├── STM32 EASY FLASH.bat     Windows  — double-click GUI launcher
├── run.sh                   Mac/Linux — ./run.sh GUI launcher
├── flash_gui.py             Cross-platform GUI    (Python/tkinter)
├── flash.py                 Cross-platform CLI    (Python)
├── flash_gui.ps1            Windows PowerShell GUI (legacy)
├── flash.bat                Windows CLI fallback
├── flash.ps1                Windows CLI fallback
├── TODO.md                  Roadmap & ideas
├── README.md                ← you are here
│
└── openocd/                 ⏳ auto-created
    ├── windows/              openocd.exe + DLLs + scripts/
    ├── macos/                openocd + .dylib + scripts/
    └── linux/                openocd + .so + scripts/
```

---

## ✅ Requirements

| Item | Notes |
|------|-------|
| **Python 3.6+** | [python.org](https://www.python.org/downloads/) — any OS |
| **Internet (first run)** | Auto-downloads OpenOCD (~8 MB) into `openocd/<os>/` |
| **`.hex` firmware file** | From your build (e.g. `build/firmware.hex`) |
| **ST-Link programmer** | v2 or v3 — plug via USB |

Everything else is **bundled** inside `easy_flash/`. No system installs, no PATH edits.

---

## 🔌 ST-Link Driver

The ST-Link programmer needs a driver to communicate with OpenOCD.

> ⚠️ **First time plugging in ST-Link?** Plug it in and wait for your OS to finish auto-install before flashing.

| OS | Normal | Troubleshooting |
|-----|--------|----------------|
| **Windows** | Plug & play ✅ | Use [Zadig](https://zadig.akeo.ie/) → install **WinUSB** if you see `LIBUSB_ERROR` |
| **macOS** | Works out of the box ✅ | `brew install libusb` |
| **Linux** | Built into kernel ✅ | `sudo apt install libusb-1.0-0-dev` |

### 🐧 WSL / Linux — missing shared library?

If you see `error while loading shared libraries` when flashing:

```bash
sudo apt update
sudo apt install libftdi1-2 libhidapi-hidraw0 libusb-1.0-0
```

The error message tells you exactly which `.so` is missing — `apt install` the matching package.

---

## 🔒 Safety Guarantees

| What we don't touch | |
|-------------------|---|
| System `PATH` | 🚫 Never modified |
| Registry / dotfiles | 🚫 Never modified |
| Admin / root rights | 🚫 Never required |
| Global installs | 🚫 Never performed |
| OpenOCD location | ✅ Only `easy_flash/openocd/<os>/` |
| Working directory | ✅ Always runs from `easy_flash/` |

---

## ❓ Manual OpenOCD Install

If the auto-download fails:

1. Download the **xPack OpenOCD** build for your OS:  
   <https://github.com/xpack-dev-tools/openocd-xpack/releases>

2. Extract → copy into the right subfolder:

   ```
   Download                  →  easy_flash/openocd/<os>/
   ──────────────────────────────────────────────────────
   Windows: bin/openocd.exe + DLLs  →  openocd/windows/
   Windows: openocd/scripts/        →  openocd/windows/scripts/

   macOS:   bin/openocd + .dylib    →  openocd/macos/
   macOS:   openocd/scripts/        →  openocd/macos/scripts/

   Linux:   bin/openocd + .so       →  openocd/linux/
   Linux:   openocd/scripts/        →  openocd/linux/scripts/
   ```

---

## ⚡ CLI for Developers

```bash
# Flash default hex
python flash.py

# Flash a specific file
python flash.py ../build/my-firmware.hex

# Custom OpenOCD configs
python flash.py firmware.hex --interface interface/jlink.cfg --target target/stm32f4x.cfg

# Platform-native fallbacks (no Python needed)
flash.bat build\firmware.hex          # Windows
./run.sh --cli ../build/firmware.hex  # macOS / Linux
```

---

## 🤝 Contributing

Contributions are welcome! A few guidelines:

1. **Keep it zeroconf** — no new dependencies that require global installs
2. **Keep it cross-platform** — test on Windows, macOS, Linux (or WSL)
3. **Open an issue first** for significant changes
4. **`pip install -r dev-requirements.txt`** if we add dev deps later

See [TODO.md](TODO.md) for the roadmap.

---

## 📄 License

Distributed under the **MIT License**. See `LICENSE` for details.

---

## 🙏 Acknowledgments

- [xPack OpenOCD](https://github.com/xpack-dev-tools/openocd-xpack) — self-contained builds for all platforms
- [OpenOCD](https://openocd.org/) — the amazing open-source debugging tool
- STMicroelectronics — for the STM32 ecosystem

---

*Made for robotics teams, hackers, and anyone who just wants to flash a chip.*

- ST-Link v2 (or v3) programmer must be connected via USB.
- After flashing, the MCU is verified and reset automatically.
- Drag-and-drop a `.hex` file onto the GUI window for quick loading.
