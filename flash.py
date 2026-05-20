#!/usr/bin/env python3
"""
STM32 EASY FLASH - Cross-platform CLI firmware flasher for STM32 via ST-Link.
Works on Windows, macOS, and Linux.
No external dependencies beyond Python 3.6+ and OpenOCD.
"""

import sys
import os
import subprocess
import argparse
import platform

# ── Paths ──────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
DEFAULT_HEX = os.path.join(PROJECT_DIR, "build", "2026-rov-Float-STM32.hex")
SYSTEM = platform.system()
EXE_NAME = "openocd.exe" if SYSTEM == "Windows" else "openocd"

# OS subfolder inside openocd/ (e.g. openocd/windows/, openocd/macos/, openocd/linux/)
OS_FOLDER = {"Windows": "windows", "Darwin": "macos", "Linux": "linux"}
OPENOCD_DIR = os.path.join(SCRIPT_DIR, "openocd", OS_FOLDER.get(SYSTEM, "linux"))


def get_openocd_path() -> str | None:
    """Return path to bundled OpenOCD (local only, never touches system PATH)."""
    bundled = os.path.join(OPENOCD_DIR, EXE_NAME)
    if os.path.isfile(bundled):
        return bundled
    return None


def get_scripts_dir(openocd_path: str) -> str | None:
    """Derive the OpenOCD scripts directory from the binary location."""
    base = os.path.dirname(openocd_path)
    # xPack layout: <base>/scripts/
    scripts = os.path.join(base, "scripts")
    if os.path.isdir(scripts):
        return scripts
    # Standard layout: <base>/share/openocd/scripts/
    scripts = os.path.join(base, "share", "openocd", "scripts")
    if os.path.isdir(scripts):
        return scripts
    return None


def flash(
    hex_path: str,
    interface_cfg: str = "interface/stlink.cfg",
    target_cfg: str = "target/stm32f1x.cfg",
) -> int:
    """Flash a .hex file to STM32 via ST-Link. Returns exit code."""
    openocd = get_openocd_path()
    if not openocd:
        print(
            "[ERROR] OpenOCD not found. Run the GUI first to auto-download it, "
            "or place it in the openocd/ folder."
        )
        return 1

    if not os.path.isfile(hex_path):
        print(f"[ERROR] Hex file not found: {hex_path}")
        return 1

    hex_forward = hex_path.replace("\\", "/")
    tcl_cmd = f"program {hex_forward} verify reset exit"

    args = []

    scripts_dir = get_scripts_dir(openocd)
    if scripts_dir:
        args += ["-s", scripts_dir]

    args += ["-f", interface_cfg, "-f", target_cfg, "-c", tcl_cmd]

    print("=" * 48)
    print(" STM32 EASY FLASH")
    print("=" * 48)
    print(f" Hex:     {hex_path}")
    print(f" OpenOCD: {openocd}")
    print(f" Target:  {target_cfg}")
    print("=" * 48)
    print()

    print(f"[INFO] Starting flash via ST-Link...\n")

    try:
        proc = subprocess.Popen(
            [openocd] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=PROJECT_DIR,
        )
        stdout_data, stderr_data = proc.communicate()
        if stdout_data:
            print(stdout_data, end="")
        if stderr_data:
            print("--- stderr ---")
            print(stderr_data, end="")

        print()
        if proc.returncode == 0:
            print("=" * 48)
            print(" >>> Flash completed successfully! <<<")
            print("=" * 48)
        else:
            print("=" * 48)
            print(f" >>> Flash FAILED! (exit code: {proc.returncode}) <<<")
            print("=" * 48)
            if proc.returncode == 127:
                print("[HINT] Exit code 127 = OS couldn't run OpenOCD.")
                print(f"       Binary: {openocd}")
                if (
                    stderr_data
                    and "error while loading shared libraries" in stderr_data
                ):
                    import re

                    match = re.search(
                        r"loading shared libraries: (.+?):",
                        stderr_data,
                    )
                    lib = match.group(1) if match else "a library"
                    print(f"       Missing library: {lib}")
                    print(
                        f"       Install: sudo apt update && sudo apt install {lib.split('.')[0]}"
                    )
                else:
                    print(
                        "       Causes: wrong binary for OS | missing shared lib | not executable"
                    )
            elif proc.returncode == 139:
                print("[HINT] Exit code 139 = segfault. Binary may be corrupted")
                print("       or incompatible. Try reinstalling OpenOCD.")
        return proc.returncode

    except FileNotFoundError:
        print(f"[ERROR] Could not execute OpenOCD at: {openocd}")
        print(
            "[HINT] Click 'Install OpenOCD' in the GUI to download the correct version."
        )
        return 1
    except Exception as e:
        print(f"[ERROR] {e}")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="STM32 EASY FLASH - Flash firmware to STM32 via ST-Link"
    )
    parser.add_argument(
        "hex_file", nargs="?", default=None, help="Path to .hex firmware file"
    )
    parser.add_argument(
        "--interface",
        "-i",
        default="interface/stlink.cfg",
        help="OpenOCD interface config (default: interface/stlink.cfg)",
    )
    parser.add_argument(
        "--target",
        "-t",
        default="target/stm32f1x.cfg",
        help="OpenOCD target config (default: target/stm32f1x.cfg)",
    )
    args = parser.parse_args()

    hex_path = args.hex_file
    if not hex_path:
        hex_path = DEFAULT_HEX
        print(f"[INFO] No hex file specified, using default: {hex_path}")
    else:
        hex_path = os.path.abspath(hex_path)

    sys.exit(flash(hex_path, args.interface, args.target))


if __name__ == "__main__":
    main()
