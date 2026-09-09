#!/usr/bin/env python3
"""Shared OpenOCD discovery + install logic.

Single source of truth for where the bundled OpenOCD lives and how the
xPack release is unpacked into that layout. Used by:

  - flash_gui.py / flash.py   (runtime auto-install fallback)
  - packaging/build.py        (CI bundling for the standalone app)

Layout produced (relative to the *bundle dir*, i.e. the directory the app
is installed in):

    openocd/
      windows/   openocd.exe + DLLs + scripts/
      macos/     openocd + scripts/
      linux/     openocd + scripts/
      libexec/   macOS .dylib / Linux .so shared libraries

The xPack binary resolves its shared libs via @loader_path/../libexec
(macOS) or $ORIGIN/../libexec (Linux), so libexec/ must sit one level above
the binary — i.e. directly under openocd/, not inside the per-OS folder.
"""

import os
import platform
import shutil
import sys
import tarfile
import tempfile
import urllib.request
import zipfile

OPENOCD_VERSION = "0.12.0-7"
OPENOCD_BASE_URL = (
    "https://github.com/xpack-dev-tools/openocd-xpack/releases/download/"
    f"v{OPENOCD_VERSION}/"
)

OS_FOLDER = {"Windows": "windows", "Darwin": "macos", "Linux": "linux"}


def exe_name(system=None):
    system = system or platform.system()
    return "openocd.exe" if system == "Windows" else "openocd"


def bundle_dir():
    """Directory the app is installed in (where openocd/ lives).

    Source runs use the script's directory. Frozen PyInstaller apps use the
    executable's directory; macOS .app bundles resolve to Contents/Resources
    (a writable, install-relative location next to the bundled resources).
    """
    if getattr(sys, "frozen", False):
        exe = os.path.abspath(sys.executable)
        d = os.path.dirname(exe)
        if sys.platform == "darwin" and os.path.basename(d) == "MacOS":
            # <name>.app/Contents/MacOS/<exe> -> <name>.app/Contents/Resources
            return os.path.abspath(os.path.join(d, "..", "Resources"))
        return d
    return os.path.dirname(os.path.abspath(__file__))


def get_openocd_path(bundle=None, system=None):
    """Return path to bundled OpenOCD, or None if not installed."""
    system = system or platform.system()
    base = bundle or bundle_dir()
    path = os.path.join(
        base, "openocd", OS_FOLDER.get(system, "linux"), exe_name(system)
    )
    return path if os.path.isfile(path) else None


def get_scripts_dir(openocd_path):
    """Derive the OpenOCD scripts directory from the binary location."""
    base = os.path.dirname(openocd_path)
    for candidate in (
        os.path.join(base, "scripts"),
        os.path.join(base, "share", "openocd", "scripts"),
    ):
        if os.path.isdir(candidate):
            return candidate
    return None


def get_openocd_download_url(system=None, machine=None):
    """xPack OpenOCD download URL for the given platform.

    xPack publishes arm64 and x64 builds for macOS and Linux, but only an
    x64 build for Windows ("win32" refers to the Windows API, not the arch).
    """
    system = system or platform.system()
    machine = (machine or platform.machine()).lower()

    os_tag = {"Windows": "win32", "Darwin": "darwin", "Linux": "linux"}.get(
        system, "linux"
    )

    if system == "Windows":
        arch, ext = "x64", "zip"
    else:
        arch = "arm64" if machine in ("arm64", "aarch64") else "x64"
        ext = "tar.gz"

    return f"{OPENOCD_BASE_URL}xpack-openocd-{OPENOCD_VERSION}-{os_tag}-{arch}.{ext}"


def install_openocd(
    bundle=None,
    system=None,
    machine=None,
    log=None,
    set_status=None,
    progress=None,
):
    """Download + unpack xPack OpenOCD into <bundle>/openocd/<os>/ (+ libexec/).

    Returns the path to the installed OpenOCD binary, or None on failure.
    Download/extraction happen in a system temp dir so the bundle dir is
    never polluted with partial archives and may even be read-only.
    """
    log = log or (lambda *a, **k: None)
    set_status = set_status or (lambda *a, **k: None)
    system = system or platform.system()
    machine = machine or platform.machine()
    bundle = bundle or bundle_dir()

    url = get_openocd_download_url(system, machine)
    os_dir = os.path.join(bundle, "openocd", OS_FOLDER.get(system, "linux"))
    openocd_root = os.path.join(bundle, "openocd")

    log(f"[INFO] Platform: {system}")
    log(f"[INFO] Download URL: {url}")
    log("")

    if os.path.isdir(os_dir):
        shutil.rmtree(os_dir)
    os.makedirs(os_dir, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="openocd_install_") as tmp:
        archive = os.path.join(tmp, "openocd_download")
        extract_temp = os.path.join(tmp, "extract")
        os.makedirs(extract_temp, exist_ok=True)

        set_status("Downloading OpenOCD...")
        urllib.request.urlretrieve(url, archive, progress)
        log("[INFO] Download complete!")

        set_status("Extracting OpenOCD...")
        if url.endswith(".zip"):
            with zipfile.ZipFile(archive, "r") as zf:
                zf.extractall(extract_temp)
        else:
            with tarfile.open(archive, "r:gz") as tf:
                tf.extractall(extract_temp)

        # xPack archives wrap everything in a single top-level dir.
        items = os.listdir(extract_temp)
        xpack_root = extract_temp
        if len(items) == 1 and os.path.isdir(
            os.path.join(extract_temp, items[0])
        ):
            xpack_root = os.path.join(extract_temp, items[0])

        # Copy the binary (and any DLLs/SOs shipped next to it).
        bin_dir = os.path.join(xpack_root, "bin")
        if not os.path.isdir(bin_dir):
            for root, _dirs, files in os.walk(xpack_root):
                if exe_name(system) in files:
                    bin_dir = root
                    break
        if os.path.isdir(bin_dir):
            for item in os.listdir(bin_dir):
                src = os.path.join(bin_dir, item)
                if os.path.isfile(src):
                    shutil.copy2(src, os.path.join(os_dir, item))
            log(f"[OK] {exe_name(system)} + libraries copied")

        # macOS/Linux shared libs resolve via ../libexec (see module doc).
        libexec_dir = os.path.join(xpack_root, "libexec")
        if os.path.isdir(libexec_dir):
            dst_libexec = os.path.join(openocd_root, "libexec")
            if os.path.isdir(dst_libexec):
                shutil.rmtree(dst_libexec)
            shutil.copytree(libexec_dir, dst_libexec)
            log("[OK] Shared libraries copied (libexec/)")

        # Scripts (interface/, target/, etc.)
        scripts_src = os.path.join(xpack_root, "openocd", "scripts")
        if not os.path.isdir(scripts_src):
            scripts_src = os.path.join(xpack_root, "scripts")
        if os.path.isdir(scripts_src):
            shutil.copytree(scripts_src, os.path.join(os_dir, "scripts"))
            log("[OK] Scripts copied (interface/, target/, etc.)")

    return get_openocd_path(bundle, system)
