# TODO

## High Priority

- [ ] **Build compiler into the app** — auto-detect CMake/Makefile, run arm-none-eabi-gcc, flash the result
- [ ] **Remove Python dependency** — compile to standalone executable (PyInstaller or similar) so no tkinter setup needed
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
- [ ] CI/CD — auto-bundle OpenOCD for all platforms
- [ ] Dark mode
- [ ] i18n / multi-language

## Done ✓

- [x] Cross-platform GUI (Python/tkinter)
- [x] Cross-platform CLI (Python)
- [x] Auto-download OpenOCD per OS
- [x] OS-specific subfolders: `openocd/windows/`, `macos/`, `linux/`
- [x] No PATH / no global installs
- [x] macOS / Linux launcher (`run.sh`)
- [x] Detailed error output (stderr capture, exit code hints)
- [x] Detect missing shared libraries on Linux/WSL and suggest fix
