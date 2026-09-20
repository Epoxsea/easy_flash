# STM32 EASY FLASH

Cross-platform firmware flasher for STM32 via ST-Link (and other OpenOCD programmers). Built on **tkinter** — no third-party runtime dependencies.

![GUI](image/gui.png)

## 🔧 Features

- **Cross-platform:** Works on Windows, macOS, and Linux.
- **No installations needed:** Everything bundled — works from source or standalone executable.
- **Supports multiple boards & programmers** (ST-Link V2/V3, J-Link, CMSIS-DAP, Black Magic Probe).
- **Easy to use:** GUI with preconfigured boards and programmable dropdowns.
- **CLI support:** Flash from terminal using `python flash.py`.
- **Auto-download OpenOCD** via the GUI or `run.sh` (no system package manager needed).

---

## 🚀 Quick Start

### From Source:
1. Unzip → launch the app
2. Click **Browse...** → select your `.hex` file
3. Connect ST-Link to the board  
4. Select a board and programmer from dropdowns
5. Click **Flash to STM32** ✅

### Using CLI:
```bash
python flash.py build/my-firmware.hex --target target/stm32f4x.cfg
```

---

## 🧠 Motivation

I work in a robotics team with people from all backgrounds — hardware, mechanical, electrical, and software. Flashing firmware onto an STM32 board should not require understanding OpenOCD, drivers, or terminal commands.

The original tool was a powerful but intimidating tool like STM32 Programmer. This project exists so **anyone on the team** can grab a `.hex` file, plug in an ST-Link, and flash in seconds — no explanations needed.

---

## 💡 Usage

### GUI (Cross-platform):
Launch `flash_gui.py` directly from source (requires Python 3 & tkinter):

```bash
python flash_gui.py
```

### CLI:
Use `flash.py` to flash firmware with optional overrides:

```bash
python flash.py build/my-firmware.hex               # Default flashing
python flash.py build/my-firmware.hex --target target/stm32f4x.cfg   # Custom board
python flash.py build/my-firmware.hex --interface interface/jlink.cfg  # Custom programmer

# List all supported boards and programmers:
python flash.py --list
```

---

## 📁 Folder Structure

```
easy_flash/
├── flash_gui.py        # GUI source (requires tkinter)
├── flash.py            # CLI source (requires Python 3)
├── flasher.py          # Shared core logic for GUI/CLI (boards, flash streaming, settings)
├── openocd_bundle.py   # Bundled OpenOCD auto-installer
├── run.sh              # Shell launcher for Linux/macOS
├── flash.bat           # Windows batch script launcher
├── README.md
└── TODO.md
```

This project uses xPack OpenOCD 0.12.0-7 and is compatible with ST-Link V2/V3, J-Link, CMSIS-DAP, and Black Magic Probe.

---

## 🖥️ Platforms Support

| Platform      | GUI    | CLI   | Standalone |
|---------------|--------|-------|------------|
| ✅ Windows     | Yes    | Yes   | Yes        |
| ✅ macOS       | Yes    | Yes   | Yes        |
| ✅ Linux       | Yes    | Yes   | Yes        |

The standalone executables (built with PyInstaller) are self-contained and require **no Python** or **tkinter installation**.

---

## 🛠️ Development

### Source Execution:
To run from source, ensure you have Python 3 and tkinter installed:

```bash
# Check if tkinter is installed
python -c "import tkinter; print('tkinter OK')"

# For macOS users (Homebrew Python)
brew install python-tk

# For Debian/Ubuntu users
sudo apt-get install python3-tk
```

Then run:

```bash
python flash_gui.py
```

### Building Standalone:
```bash
pip install pyinstaller
pyinstaller --onefile --windowed flash_gui.py
```

---

## 🔁 History of Changes

This project was inspired by [STM32 Programmer](https://gitlab.com/stm32_programmer) and the original Windows-only tool created by a teammate.

All changes since v1.0 are designed to make it:
- Cross-platform (Windows/macOS/Linux)  
- Standalone executable-ready (PyInstaller support)  
- Easy-to-use for non-coders (dropdowns/defaults)  
- Built on reusable components (flasher module)  

---

## 📦 Packaging

All builds are made using:
- Python 3.11  
- xPack OpenOCD 0.12.0-7  
- PyInstaller for standalone bundles  

The source code will work correctly with `flash.py` and `flash_gui.py` as entry points.

---

## 🧾 License

MIT