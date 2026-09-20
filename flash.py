#!/usr/bin/env python3
"""STM32 EASY FLASH - Cross-platform CLI firmware flasher for STM32 via ST-Link.

Usage:
    python flash.py <path/to/firmware.hex>  # Flash default board (F1x)

Examples:
    python flash.py build/my-firmware.hex        # Flash a custom hex file
    python flash.py --target target/stm32f4x.cfg   # Flash with F4X
    python flash.py --interface interface/jlink.cfg # Use J-Link
    python flash.py --list                         # List supported boards
    python flash.py --help                        # Show this help

Flash command-line options:
    -i, --interface  OpenOCD interface config (default: interface/stlink.cfg)
    -t, --target     OpenOCD target config (default: target/stm32f1x.cfg)

Note: All paths are relative to the current directory unless absolute.
Use this script from source only — for standalone executables, use:
  Windows:  flash.bat
  Linux/macOS:  ./run.sh

This script uses a bundled copy of OpenOCD. If your build requires a
custom path, you must set PYTHONPATH to include the location of the GUI's source.
"""

import argparse
import os
import sys

from openocd_bundle import bundle_dir, get_openocd_path, get_scripts_dir
import flasher

DEFAULT_HEX = "build/2026-rov-Float-STM32.hex"


def main():
    parser = argparse.ArgumentParser(
        description="STM32 EASY FLASH - Flash firmware to STM32 via ST-Link",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Example: python flash.py build/firmware.hex --target target/stm32f4x.cfg"""
    )
    parser.add_argument(
        "hex_file", nargs="?", help="Path to .hex firmware file (required)"
    )
    parser.add_argument(
        "--interface", "-i",
        default="interface/stlink.cfg",
        help="OpenOCD interface config (default: interface/stlink.cfg)"
    )
    parser.add_argument(
        "--target", "-t",
        default="target/stm32f1x.cfg",
        help="OpenOCD target config (default: target/stm32f1x.cfg)"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all supported boards and programmers"
    )

    args = parser.parse_args()

    # List mode: show discoverable boards
    if args.list:
        _list_configs()
        return

    hex_path = args.hex_file
    if not hex_path:
        print("Error: No firmware file specified.\n", file=sys.stderr)
        parser.print_usage()
        print("\nNote: The script requires a hex file as an argument.\n", file=sys.stderr)
        sys.exit(1)

    # Expand to full path
    hex_path = os.path.abspath(hex_path)

    if not os.path.isfile(hex_path):
        print(f"[ERROR] Hex file not found: {hex_path}")
        sys.exit(1)

    openocd = get_openocd_path()
    if not openocd:
        print("[ERROR] OpenOCD is missing. Run the GUI first to auto-download it.")
        sys.exit(1)

    scripts_dir = get_scripts_dir(openocd)
    rc = flasher.flash(
        openocd,
        args.interface,
        args.target,
        hex_path,
        scripts_dir=scripts_dir,
        log=lambda text: print(text, flush=True)
    )

    if rc == 0:
        print("=" * 48)
        print(" >>> Flash completed successfully! <<<")
        print("=" * 48)
    else:
        print("=" * 48)
        print(f" >>> Flash FAILED! (exit code: {rc}) <<<")
        print("=" * 48)

        hints = flasher.describe_failure(rc, "")
        for hint in hints:
            print(hint)

    sys.exit(rc)


def _list_configs():
    """Show all discovered boards and programmers."""
    print("\nSupported STM32 Target Boards:")
    print("-" * 40)
    openocd = get_openocd_path()
    scripts = get_scripts_dir(openocd) if openocd else None
    for label, path in flasher.list_targets(scripts):
        print(f"  {label}")
    print()

    print("Supported Programmers:")
    print("-" * 40)
    for label, path in flasher.list_programmers(scripts):
        print(f"  {label} ({os.path.basename(path)[:-4]})")
    print("\nUse --target and --interface to select a specific board or programmer.")

if __name__ == "__main__":
    main()