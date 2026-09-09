#!/usr/bin/env python3
"""Build the standalone GUI app and bundle OpenOCD for one target OS/arch.

Run from the repo root (CI does exactly this):

    python packaging/build.py --os windows|macos|linux --arch x64|arm64

Produces `dist/EasyFlash-<os>-<arch>.zip` containing the PyInstaller output
plus the bundled OpenOCD for that platform, so the end user just unzips and
runs — no Python, no tkinter setup, no PATH changes.

Cross-compilation note: PyInstaller does not cross-compile, so this must run
on the target OS (Windows/macOS/Linux runners in CI).
"""

import argparse
import os
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

APP_NAME = "EasyFlash"
SYSTEM_MAP = {"windows": "Windows", "macos": "Darwin", "linux": "Linux"}

README = """\
STM32 EASY FLASH - portable firmware flasher for STM32 via ST-Link.

How to flash:
  1. Double-click {exe} to start the GUI.
  2. Click "Browse..." and pick your .hex firmware file.
  3. Connect your ST-Link to the board and click "Flash to STM32".

OpenOCD is already bundled inside this folder - no install, no Python,
no PATH changes. If the ST-Link needs a driver, see the project README.
"""


def run(cmd, cwd):
    print("+", " ".join(cmd))
    subprocess.check_call(cmd, cwd=cwd)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--os", dest="os_name", required=True, choices=sorted(SYSTEM_MAP)
    )
    ap.add_argument("--arch", required=True, choices=["x64", "arm64"])
    args = ap.parse_args()

    system = SYSTEM_MAP[args.os_name]
    dist = os.path.join(ROOT, "dist")
    work = os.path.join(ROOT, "build")

    shutil.rmtree(dist, ignore_errors=True)
    shutil.rmtree(work, ignore_errors=True)

    sys.path.insert(0, ROOT)
    import openocd_bundle as ob

    # 1. Build the GUI with PyInstaller.
    pyi = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--name",
        APP_NAME,
        "--distpath",
        dist,
        "--workpath",
        work,
        "--specpath",
        os.path.join(ROOT, "packaging"),
    ]
    if args.os_name in ("windows", "macos"):
        pyi.append("--windowed")
    pyi.append(os.path.join(ROOT, "flash_gui.py"))
    run(pyi, ROOT)

    # 2. Where OpenOCD must live (must match bundle_dir() in openocd_bundle.py).
    if args.os_name == "macos":
        app_dir = os.path.join(dist, APP_NAME + ".app", "Contents", "Resources")
    else:
        app_dir = os.path.join(dist, APP_NAME)
    os.makedirs(app_dir, exist_ok=True)

    # 3. Bundle OpenOCD for this platform.
    result = ob.install_openocd(
        app_dir, system=system, machine=args.arch, log=print
    )
    if not result:
        raise SystemExit("OpenOCD bundling failed")

    # 4. Drop a short README next to the binary.
    exe = ob.exe_name(system)
    with open(os.path.join(app_dir, "README.txt"), "w") as f:
        f.write(README.format(exe=exe))

    # 5. Zip for distribution.
    zip_path = os.path.join(dist, f"{APP_NAME}-{args.os_name}-{args.arch}.zip")
    if args.os_name == "macos":
        app_root = os.path.join(dist, APP_NAME + ".app")
        arc_root = APP_NAME + ".app"
    else:
        app_root = os.path.join(dist, APP_NAME)
        arc_root = APP_NAME

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(app_root):
            for name in files:
                full = os.path.join(root, name)
                arc = os.path.join(arc_root, os.path.relpath(full, app_root))
                zf.write(full, arc)

    print("Built:", zip_path)


if __name__ == "__main__":
    main()
