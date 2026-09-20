#!/usr/bin/env python3
"""Shared flash engine — single source of truth for the GUI (flash_gui.py)
and the CLI (flash.py).

Handles:
  - board / programmer discovery (dropdown lists, from the bundled OpenOCD
    scripts when present, curated defaults otherwise)
  - building the OpenOCD command line (Tcl-safe quoting of firmware paths)
  - pre-flash adapter detection ("is a programmer actually connected?")
  - streaming OpenOCD output live (no more buffering everything until the
    end) with optional cancellation
  - platform failure hints (missing shared libs, corrupt binary, ...)

Pure standard library; no third-party dependencies.
"""

import os
import re
import subprocess

DEFAULT_INTERFACE = "interface/stlink.cfg"
DEFAULT_TARGET = "target/stm32f1x.cfg"

# Fallback board list, used when the bundled OpenOCD scripts are not installed
# yet so the dropdown is never empty. Mirrors the STM32 targets shipped in
# OpenOCD 0.12 (verified against the xPack 0.12.0-7 scripts/ directory).
DEFAULT_TARGETS = [
    ("STM32C0x", "target/stm32c0x.cfg"),
    ("STM32F0x", "target/stm32f0x.cfg"),
    ("STM32F1x", "target/stm32f1x.cfg"),
    ("STM32F2x", "target/stm32f2x.cfg"),
    ("STM32F3x", "target/stm32f3x.cfg"),
    ("STM32F4x", "target/stm32f4x.cfg"),
    ("STM32F7x", "target/stm32f7x.cfg"),
    ("STM32G0x", "target/stm32g0x.cfg"),
    ("STM32G4x", "target/stm32g4x.cfg"),
    ("STM32H7x", "target/stm32h7x.cfg"),
    ("STM32H7x (dual bank)", "target/stm32h7x_dual_bank.cfg"),
    ("STM32L0x", "target/stm32l0.cfg"),
    ("STM32L0x (dual bank)", "target/stm32l0_dual_bank.cfg"),
    ("STM32L1x", "target/stm32l1.cfg"),
    ("STM32L1x (dual bank)", "target/stm32l1x_dual_bank.cfg"),
    ("STM32L4x", "target/stm32l4x.cfg"),
    ("STM32L5x", "target/stm32l5x.cfg"),
    ("STM32U0x", "target/stm32u0x.cfg"),
    ("STM32U3x", "target/stm32u3x.cfg"),
    ("STM32U5x", "target/stm32u5x.cfg"),
    ("STM32W108", "target/stm32w108xx.cfg"),
    ("STM32WBAx", "target/stm32wbax.cfg"),
    ("STM32WBx", "target/stm32wbx.cfg"),
    ("STM32WLx", "target/stm32wlx.cfg"),
    ("STM32XL", "target/stm32xl.cfg"),
]

FAMILY_LABELS = {path: label for label, path in DEFAULT_TARGETS}

DEFAULT_PROGRAMMERS = [
    ("ST-Link", "interface/stlink.cfg"),
    ("J-Link", "interface/jlink.cfg"),
    ("CMSIS-DAP", "interface/cmsis-dap.cfg"),
    ("CMSIS-DAP (TCP)", "interface/cmsis-dap-tcp.cfg"),
    ("R-Link", "interface/rlink.cfg"),
    ("eStick", "interface/estick.cfg"),
]


def _pretty(name):
    """target/stm32f1x.cfg -> STM32F1x (fallback label for new targets)."""
    base = os.path.basename(name)
    base = base[:-4] if base.endswith(".cfg") else base
    if base.lower().startswith("stm32"):
        return "STM32" + base[5:].upper()
    return base


def _scan(scripts_dir, sub, keep, drop=()):
    root = os.path.join(scripts_dir, sub)
    if not os.path.isdir(root):
        return []
    out = []
    for entry in sorted(os.listdir(root)):
        if not entry.endswith(".cfg"):
            continue
        name = entry[:-4]
        if not keep(name) or any(d in name for d in drop):
            continue
        out.append((name, os.path.join(sub, entry)))
    return out


def list_targets(scripts_dir=None):
    """Ordered [(label, cfg path)] for every flashable STM32 board.

    Scans the OpenOCD ``target/`` directory when available; otherwise falls
    back to the curated DEFAULT_TARGETS. Internal helper configs (e.g.
    ``stm32x5x_common.cfg``) are excluded.
    """
    if scripts_dir:
        found = _scan(
            scripts_dir,
            "target",
            keep=lambda n: n.lower().startswith("stm32"),
            drop=("_common",),
        )
        if found:
            return [(FAMILY_LABELS.get(p, _pretty(p)), p) for _p, p in found]
    return list(DEFAULT_TARGETS)


def list_programmers(scripts_dir=None):
    """Ordered [(label, cfg path)] for OpenOCD programmers.

    ST-Link first (default), the rest alphabetical; falls back to a curated
    list when the scripts directory is unavailable.
    """
    if scripts_dir:
        found = _scan(scripts_dir, "interface", keep=lambda n: True)
        if found:
            found.sort(key=lambda item: (item[1] != "interface/stlink.cfg", item[1]))
            return [(name, path) for name, path in found]
    return list(DEFAULT_PROGRAMMERS)


def tcl_path(path):
    """Make a filesystem path safe inside a Tcl double-quoted string."""
    # Tcl handles forward slashes on Windows; backslashes are an escape
    # character inside double quotes. Convert backslashes to slashes first,
    # then escape any literal quotes (the backslashes added here are the
    # only ones left, so they must stay intact).
    return path.replace("\\", "/").replace('"', '\\"')


def build_flash_argv(openocd, interface_cfg, target_cfg, hex_path, scripts_dir=None):
    """Full OpenOCD command line for one flash operation.

    -c commands run in order: pick the classic SWD transport (deterministic
    across ST-Link v2/v3 and other programmers on OpenOCD >= 0.12), then
    program/verify/reset, then exit.
    """
    argv = [openocd]
    if scripts_dir:
        argv += ["-s", scripts_dir]
    argv += [
        "-f", interface_cfg,
        "-f", target_cfg,
        "-c", "transport select swd",
        "-c", f'program "{tcl_path(hex_path)}" verify reset exit',
    ]
    return argv


def build_detect_argv(openocd, interface_cfg, scripts_dir=None):
    """OpenOCD command line that fails unless a programmer is connected."""
    argv = [openocd]
    if scripts_dir:
        argv += ["-s", scripts_dir]
    argv += [
        "-f", interface_cfg,
        "-c", "transport select swd",
        "-c", "adapter init",
        "-c", "adapter list",
        "-c", "exit",
    ]
    return argv


def _popen(argv):
    # Merge stderr into stdout so log lines keep their original order and the
    # consumer can stream them; replace undecodable bytes instead of crashing.
    # Creation flags for reliable kill/termination on Windows.
    kwargs = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "text": True,
        "errors": "replace",
        "bufsize": 1,
    }
    if os.name == "nt":
        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
    return subprocess.Popen(argv, **kwargs)


def detect_programmer(openocd, interface_cfg, scripts_dir=None, log=None):
    """Try to attach OpenOCD to the programmer. Returns (ok, lines).

    ``open failed`` (or any non-zero exit) means no usable programmer is
    connected for that interface config.
    """
    log = log or (lambda *_a: None)
    try:
        proc = _popen(build_detect_argv(openocd, interface_cfg, scripts_dir))
        out, _ = proc.communicate(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
        return False, ["[ERROR] Adapter detection timed out."]
    lines = [ln.rstrip("\n") for ln in out.splitlines()]
    return proc.returncode == 0, lines


def flash(
    openocd,
    interface_cfg,
    target_cfg,
    hex_path,
    scripts_dir=None,
    log=None,
    cancel=None,
):
    """Run the flash and stream OpenOCD output live via ``log``.

    ``cancel``: optional zero-arg callable; when it starts returning truthy
    the OpenOCD process is killed (GUI Cancel button). Returns the process
    exit code.
    """
    log = log or (lambda *_a: None)
    argv = build_flash_argv(openocd, interface_cfg, target_cfg, hex_path, scripts_dir)
    proc = _popen(argv)
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            if cancel is not None and cancel():
                proc.kill()
                log("")
                log("[CANCEL] Aborted by user.", "orange")
                break
            log(line.rstrip("\n"))
    finally:
        try:
            proc.stdout.close()
        except OSError:
            pass
    return proc.wait()


def describe_failure(rc, output=""):
    """Human hints for common OpenOCD failure modes. Returns a list of lines."""
    hints = []
    if rc == 0:
        return hints
    m = re.search(r"loading shared libraries: ([\w.+-]+):", output)
    if m:
        lib = m.group(1)
        hints += [
            "[HINT] Missing shared library: %s" % lib,
            "       Debian/Ubuntu:  sudo apt install %s" % lib,
            "       Fedora:         sudo dnf install %s" % lib,
            "       (the .so name maps 1:1 to a system package on both)",
        ]
        return hints
    if "error while loading shared libraries" in output:
        hints += [
            "[HINT] A shared library is missing. Install the usual set:",
            "       sudo apt install libusb-1.0-0 libhidapi-hidraw0",
        ]
        return hints
    if rc == 127:
        hints += [
            "[HINT] The OS could not execute OpenOCD (exit 127).",
            "       macOS/Linux: run  chmod +x  on the openocd binary",
            "                    (right next to the GUI executable).",
        ]
        return hints
    if rc in (134, 139):
        hints += [
            "[HINT] OpenOCD crashed (%s). The bundled binary may not match "
            "this OS/architecture" % ("SIGABRT" if rc == 134 else "segfault"),
            "       — click 'Reinstall OpenOCD' to re-download it.",
        ]
        return hints
    if "open failed" in output or not_found_hardware(output):
        hints += [
            "[HINT] No programmer was detected. Checks:",
            "       - ST-Link plugged in (USB), board powered",
            "       - Right programmer selected in the 'Programmer' dropdown",
            "       - Windows: install the WinUSB driver via Zadig if USB errors show",
        ]
        return hints
    return hints


def not_found_hardware(output):
    return "Error: open failed" in output or "OpenOCD init failed" in output
