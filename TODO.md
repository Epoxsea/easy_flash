# TODO

## High Priority

- [ ] **Build compiler into the app** — auto-detect CMake/Makefile, run arm-none-eabi-gcc, flash the result
- [ ] Support other programmers (J-Link, CMSIS-DAP, Black Magic Probe)
- [ ] Support other target MCUs (STM32F4, STM32G0, STM32H7, etc.)

## Medium Priority

- [ ] Progress bar for flash operation
- [ ] Remember last-used `.hex` file path
- [ ] Detect ST-Link connection before flashing
- [ ] Test on native ARM macOS (Apple Silicon)
- [ ] Test on bare-metal Linux

## Lower Priority

- [ ] DFU (USB) flashing mode
- [ ] Wireless flashing (ESP-Link)
- [ ] Web-based UI option
- [ ] Dark mode
- [ ] i18n / multi-language

## Done ✓

- Cross-platform GUI (Python/tkinter)
- Cross-platform CLI (Python)
- Auto-download OpenOCD per OS
- OS-specific subfolders: `openocd/windows/`, `macos/`, `linux/`
- No PATH / no global installs
- macOS / Linux launcher (`run.sh`)
- Detailed error output (stderr capture, exit code hints)
- Detect missing shared libraries on Linux/WSL and suggest fix
- Standalone executables — no Python/tkinter install needed (PyInstaller)
- CI/CD — GitHub Actions builds + bundles OpenOCD for Windows/macOS/Linux
- Shared core refactored (`flasher.py`)
- Fixed Tcl/Tk macOS standalone pathing bug
- GUI uses dropdown menus with "Custom..." entries
- Settings persist via `easyflash.json`
- Drag-and-drop support in UI
- Cancel flash button
- Reinstall OpenOCD button
- Improved CLI with `--list`, `--target`, `--interface` options
- Updated documentation and project structure