#!/usr/bin/env python3
"""
STM32 EASY FLASH GUI - Cross-platform firmware flasher for STM32 via ST-Link.
Works on Windows, macOS, and Linux using tkinter (built-in Python GUI).
Completely self-contained — uses only bundled OpenOCD from the openocd/ folder,
never touches system PATH or global environment.
"""

import os
import platform
import subprocess
import threading
import urllib.request
import zipfile
import shutil
import tarfile
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

# ── Paths ──────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
OPENOCD_DIR = os.path.join(SCRIPT_DIR, "openocd")
OPENOCD_ARCHIVE = os.path.join(SCRIPT_DIR, "openocd.zip")

# Default OpenOCD configs (relative paths for bundled scripts/)
DEFAULT_INTERFACE_CFG = "interface/stlink.cfg"
DEFAULT_TARGET_CFG = "target/stm32f1x.cfg"

# OpenOCD download URLs per platform
OPENOCD_URLS = {
    "Windows": (
        "https://github.com/xpack-dev-tools/openocd-xpack/releases/download/v0.12.0-1/"
        "xpack-openocd-0.12.0-1-win32-x64.zip"
    ),
    "Darwin": (  # macOS
        "https://github.com/xpack-dev-tools/openocd-xpack/releases/download/v0.12.0-1/"
        "xpack-openocd-0.12.0-1-darwin-x64.zip"
    ),
    "Linux": (
        "https://github.com/xpack-dev-tools/openocd-xpack/releases/download/v0.12.0-1/"
        "xpack-openocd-0.12.0-1-linux-x64.tar.gz"
    ),
}

SYSTEM = platform.system()
EXE_NAME = "openocd.exe" if SYSTEM == "Windows" else "openocd"

# OS subfolder inside openocd/ (e.g. openocd/windows/, openocd/macos/, openocd/linux/)
OS_FOLDER = {"Windows": "windows", "Darwin": "macos", "Linux": "linux"}
OPENOCD_OS_DIR = os.path.join(SCRIPT_DIR, "openocd", OS_FOLDER.get(SYSTEM, "linux"))


# ── Helpers ────────────────────────────────────────────────────────────────


def get_openocd_path() -> str | None:
    """Return path to bundled OpenOCD (local only, never system PATH)."""
    bundled = os.path.join(OPENOCD_OS_DIR, EXE_NAME)
    return bundled if os.path.isfile(bundled) else None


def get_scripts_dir(openocd_path: str) -> str | None:
    """Derive scripts directory from bundled OpenOCD location."""
    base = os.path.dirname(openocd_path)
    for candidate in [
        os.path.join(base, "scripts"),
        os.path.join(base, "share", "openocd", "scripts"),
    ]:
        if os.path.isdir(candidate):
            return candidate
    return None


def get_openocd_download_url() -> str:
    """Get the appropriate OpenOCD download URL for the current platform."""
    platform_key = SYSTEM
    if platform_key not in OPENOCD_URLS:
        # Fallback: try Linux URL as generic
        platform_key = "Linux"
    return OPENOCD_URLS[platform_key]


# ── GUI Application ────────────────────────────────────────────────────────


class FlashGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("STM32 EASY FLASH")
        self.root.geometry("780x660")
        self.root.resizable(False, False)
        self.root.configure(bg="#ffffff")

        # Center window
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"+{x}+{y}")

        # State
        self.interface_cfg = DEFAULT_INTERFACE_CFG
        self.target_cfg = DEFAULT_TARGET_CFG
        self.is_flashing = False

        self._build_ui()
        self._on_startup()

    # ── UI Construction ────────────────────────────────────────────────

    def _build_ui(self):
        # ── Title bar ──
        title_frame = tk.Frame(self.root, bg="#0067c0", height=60)
        title_frame.pack(fill="x")
        title_frame.pack_propagate(False)

        tk.Label(
            title_frame,
            text="STM32",
            fg="white",
            bg="#0067c0",
            font=("Segoe UI", 18, "bold"),
        ).place(x=10, y=2)
        tk.Label(
            title_frame,
            text="EASY FLASH",
            fg="#b4d2ff",
            bg="#0067c0",
            font=("Segoe UI", 13),
        ).place(x=106, y=5)
        tk.Label(
            title_frame,
            text="ST-Link Firmware Flasher  |  No coding, no setup, just flash!",
            fg="#c8dcff",
            bg="#0067c0",
            font=("Segoe UI", 9),
        ).place(x=10, y=34)

        main_frame = tk.Frame(self.root, bg="#ffffff", padx=12, pady=6)
        main_frame.pack(fill="both", expand=True)

        # ── Firmware file section ──
        file_frame = tk.LabelFrame(
            main_frame,
            text="Firmware File (.hex)",
            font=("Segoe UI", 10),
            padx=6,
            pady=4,
        )
        file_frame.pack(fill="x", pady=(4, 4))

        frow = tk.Frame(file_frame)
        frow.pack(fill="x")
        self.hex_var = tk.StringVar(value="Select a .hex file or drag it here...")
        self.hex_entry = tk.Entry(
            frow, textvariable=self.hex_var, font=("Segoe UI", 10), fg="gray"
        )
        self.hex_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.hex_entry.bind("<Button-1>", lambda e: self._browse_hex())

        tk.Button(
            frow, text="Browse...", command=self._browse_hex, font=("Segoe UI", 9)
        ).pack(side="right")

        # ── Config files section ──
        cfg_frame = tk.LabelFrame(
            main_frame,
            text="OpenOCD Config Files",
            font=("Segoe UI", 10),
            padx=6,
            pady=4,
        )
        cfg_frame.pack(fill="x", pady=(2, 4))

        # Interface row
        irow = tk.Frame(cfg_frame)
        irow.pack(fill="x", pady=1)
        tk.Label(
            irow, text="Interface:", font=("Segoe UI", 9), width=8, anchor="w"
        ).pack(side="left")
        self.int_var = tk.StringVar(value=DEFAULT_INTERFACE_CFG)
        tk.Entry(irow, textvariable=self.int_var, font=("Segoe UI", 9)).pack(
            side="left", fill="x", expand=True, padx=(0, 4)
        )
        tk.Button(
            irow,
            text="Browse...",
            font=("Segoe UI", 8),
            command=lambda: self._browse_cfg("interface"),
        ).pack(side="left")
        reset_int = tk.Label(
            irow,
            text="reset",
            fg="gray",
            cursor="hand2",
            font=("Segoe UI", 8, "underline"),
        )
        reset_int.pack(side="left", padx=(6, 0))
        reset_int.bind("<Button-1>", lambda e: self.int_var.set(DEFAULT_INTERFACE_CFG))

        # Target row
        trow = tk.Frame(cfg_frame)
        trow.pack(fill="x", pady=1)
        tk.Label(trow, text="Target:", font=("Segoe UI", 9), width=8, anchor="w").pack(
            side="left"
        )
        self.tgt_var = tk.StringVar(value=DEFAULT_TARGET_CFG)
        tk.Entry(trow, textvariable=self.tgt_var, font=("Segoe UI", 9)).pack(
            side="left", fill="x", expand=True, padx=(0, 4)
        )
        tk.Button(
            trow,
            text="Browse...",
            font=("Segoe UI", 8),
            command=lambda: self._browse_cfg("target"),
        ).pack(side="left")
        reset_tgt = tk.Label(
            trow,
            text="reset",
            fg="gray",
            cursor="hand2",
            font=("Segoe UI", 8, "underline"),
        )
        reset_tgt.pack(side="left", padx=(6, 0))
        reset_tgt.bind("<Button-1>", lambda e: self.tgt_var.set(DEFAULT_TARGET_CFG))

        # ── Buttons ──
        btn_frame = tk.Frame(main_frame)
        btn_frame.pack(fill="x", pady=(4, 4))

        self.flash_btn = tk.Button(
            btn_frame,
            text=">  Flash to STM32",
            font=("Segoe UI", 10, "bold"),
            bg="#0078d7",
            fg="white",
            command=self._on_flash,
            cursor="hand2",
            relief="flat",
            padx=10,
            pady=6,
        )
        self.flash_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.install_btn = tk.Button(
            btn_frame,
            text="Install OpenOCD",
            font=("Segoe UI", 10),
            bg="#505050",
            fg="white",
            command=self._on_install,
            cursor="hand2",
            relief="flat",
            padx=10,
            pady=6,
        )
        self.install_btn.pack(side="left", fill="x", expand=True, padx=(4, 0))

        # Hover effects
        self.flash_btn.bind(
            "<Enter>",
            lambda e: (
                self.flash_btn.configure(bg="#008ceb")
                if self.flash_btn["state"] != "disabled"
                else None
            ),
        )
        self.flash_btn.bind(
            "<Leave>",
            lambda e: (
                self.flash_btn.configure(bg="#0078d7")
                if self.flash_btn["state"] != "disabled"
                else None
            ),
        )
        self.install_btn.bind(
            "<Enter>", lambda e: self.install_btn.configure(bg="#646464")
        )
        self.install_btn.bind(
            "<Leave>", lambda e: self.install_btn.configure(bg="#505050")
        )

        # ── Output log ──
        out_frame = tk.LabelFrame(
            main_frame, text="Output Log", font=("Segoe UI", 10), padx=6, pady=4
        )
        out_frame.pack(fill="both", expand=True)

        self.output = scrolledtext.ScrolledText(
            out_frame,
            font=("Consolas", 10),
            bg="#1e1e1e",
            fg="#d4d4d4",
            relief="flat",
            borderwidth=1,
            state="disabled",
            wrap="word",
        )
        self.output.pack(fill="both", expand=True)

        # Text tag colors
        self.output.tag_configure("green", foreground="#4ec94e")
        self.output.tag_configure("red", foreground="#f44747")
        self.output.tag_configure("blue", foreground="#569cd6")
        self.output.tag_configure("cyan", foreground="#4ec9b0")
        self.output.tag_configure("orange", foreground="#ce9178")
        self.output.tag_configure("gray", foreground="#808080")
        self.output.tag_configure("white", foreground="#d4d4d4")

        self._log("Welcome to STM32 EASY FLASH!", "blue")
        self._log("")
        self._log("Instructions:", "white")
        self._log("  1. Click 'Browse...' to select a .hex file", "gray")
        self._log("  2. Connect ST-Link to your board", "gray")
        self._log("  3. Click 'Flash to STM32'", "gray")
        self._log("")
        self._log("You can also drag-and-drop a .hex file onto this window.", "gray")

        # Drag-and-drop support
        self._enable_drag_drop()

        # ── Status bar ──
        status_frame = tk.Frame(self.root, bg="#f0f0f0", height=26)
        status_frame.pack(fill="x")
        status_frame.pack_propagate(False)

        self.status_label = tk.Label(
            status_frame,
            text="Initializing...",
            fg="gray",
            bg="#f0f0f0",
            font=("Segoe UI", 9),
            anchor="w",
            padx=10,
        )
        self.status_label.pack(side="left", fill="x", expand=True)

        tk.Label(
            status_frame,
            text="v2.0",
            fg="gray",
            bg="#f0f0f0",
            font=("Segoe UI", 9),
            padx=10,
        ).pack(side="right")

    # ── UI Actions ────────────────────────────────────────────────────

    def _log(self, text, tag=None):
        self.output.configure(state="normal")
        if tag:
            self.output.insert("end", text + "\n", tag)
        else:
            self.output.insert("end", text + "\n")
        self.output.see("end")
        self.output.configure(state="disabled")
        self.root.update_idletasks()

    def _set_status(self, text, color="gray"):
        self.status_label.configure(text=text, fg=color)

    def _browse_hex(self):
        path = filedialog.askopenfilename(
            title="Select firmware hex file",
            filetypes=[("Hex files", "*.hex"), ("All files", "*.*")],
            initialdir=(
                os.path.join(PROJECT_DIR, "build")
                if os.path.isdir(os.path.join(PROJECT_DIR, "build"))
                else SCRIPT_DIR
            ),
        )
        if path:
            self.hex_var.set(path)
            self.hex_entry.configure(fg="black")

    def _browse_cfg(self, cfg_type):
        path = filedialog.askopenfilename(
            title=f"Select {cfg_type} config file",
            filetypes=[("Config files", "*.cfg"), ("All files", "*.*")],
        )
        if path:
            if cfg_type == "interface":
                self.int_var.set(path)
            else:
                self.tgt_var.set(path)

    def _enable_drag_drop(self):
        """Register drag-drop via tkinterdnd if available; else note it."""
        # Basic Windows drag-drop support via tkinter is limited.
        # On Windows, users can paste path or use Browse.
        pass

    # ── Flashing ──────────────────────────────────────────────────────

    def _on_flash(self):
        if self.is_flashing:
            return
        hex_path = self.hex_var.get()
        if not os.path.isfile(hex_path):
            messagebox.showwarning(
                "No File Selected", "Please select a valid .hex file first."
            )
            return
        openocd = get_openocd_path()
        if not openocd:
            messagebox.showwarning(
                "OpenOCD Missing",
                "OpenOCD is not available. Click 'Install OpenOCD' first.",
            )
            return

        self.is_flashing = True
        self.flash_btn.configure(state="disabled")
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")

        self._log("=" * 44, "blue")
        self._log(" STM32 EASY FLASH", "blue")
        self._log("=" * 44, "blue")
        self._log(f" Hex: {hex_path}", "cyan")
        self._log(f" OpenOCD: {openocd} (bundled)", "cyan")
        self._log("=" * 44, "blue")
        self._log("")

        # Run flash in background thread
        thread = threading.Thread(
            target=self._run_flash, args=(hex_path, openocd), daemon=True
        )
        thread.start()

    def _run_flash(self, hex_path, openocd):
        hex_forward = hex_path.replace("\\", "/")
        tcl_cmd = f"program {hex_forward} verify reset exit"

        # Read current config from UI
        int_cfg = self.int_var.get()
        tgt_cfg = self.tgt_var.get()

        args = []
        scripts_dir = get_scripts_dir(openocd)
        if scripts_dir:
            args += ["-s", scripts_dir]
            self._log(f"[INFO] Scripts dir: {scripts_dir}", "cyan")
        args += ["-f", int_cfg, "-f", tgt_cfg, "-c", tcl_cmd]

        self._log(f"       {openocd} {' '.join(args)}", "gray")
        self._log("")
        self._log("[INFO] Starting flash via ST-Link...", "green")

        try:
            proc = subprocess.Popen(
                [openocd] + args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=PROJECT_DIR,
            )
            # Read both stdout and stderr
            stdout_data, stderr_data = proc.communicate()
            if stdout_data:
                for line in stdout_data.splitlines():
                    self._log(line, "gray")
            if stderr_data:
                self._log("--- stderr ---", "orange")
                for line in stderr_data.splitlines():
                    self._log(line, "orange")

            self._log("")
            if proc.returncode == 0:
                self._log("=" * 44, "green")
                self._log(" >>> Flash completed successfully! <<<", "green")
                self._log("=" * 44, "green")
                self.root.after(
                    0, self._set_status, "Ready - Last flash: SUCCESS", "green"
                )
                self.root.after(0, self.flash_btn.configure, {"bg": "#90ee90"})
            else:
                self._log("=" * 44, "red")
                self._log(
                    f" >>> Flash FAILED! (exit code: {proc.returncode}) <<<", "red"
                )
                self._log("=" * 44, "red")
                # Add helpful hints for common exit codes
                if proc.returncode == 127:
                    self._log(
                        "[HINT] Exit code 127 means the OS couldn't run OpenOCD.",
                        "orange",
                    )
                    self._log(
                        f"       Binary: {openocd}",
                        "orange",
                    )
                    # Check if stderr contains a missing shared library
                    if (
                        stderr_data
                        and "error while loading shared libraries" in stderr_data
                    ):
                        # Extract the library name from the error
                        import re

                        match = re.search(
                            r"loading shared libraries: (.+?):",
                            stderr_data,
                        )
                        lib = match.group(1) if match else "a library"
                        self._log(
                            f"       Missing library: {lib}",
                            "orange",
                        )
                        self._log(
                            f"       Install it with your package manager:",
                            "orange",
                        )
                        self._log(
                            f"         sudo apt update && sudo apt install {lib.split('.')[0]}",
                            "orange",
                        )
                        self._log(
                            f"       Or if unsure, run:  sudo apt install libftdi1-2 libusb-1.0-0 libhidapi-libusb0",
                            "orange",
                        )
                    else:
                        self._log(
                            "       Possible causes:",
                            "orange",
                        )
                        self._log(
                            "         - Wrong binary for this OS",
                            "orange",
                        )
                        self._log(
                            "         - Shared library missing (run 'ldd openocd' to check)",
                            "orange",
                        )
                        self._log(
                            "         - File is not executable (run 'chmod +x openocd')",
                            "orange",
                        )
                elif proc.returncode == 139:
                    self._log(
                        "[HINT] Exit code 139 = segfault. The OpenOCD binary may be corrupted",
                        "orange",
                    )
                    self._log(
                        "       or incompatible with this system. Try reinstalling.",
                        "orange",
                    )
                self.root.after(
                    0, self._set_status, "Ready - Last flash: FAILED", "red"
                )
        except FileNotFoundError:
            self._log(f"[ERROR] OpenOCD binary not found at: {openocd}", "red")
            self._log(
                "[HINT] Click 'Install OpenOCD' to download the correct version.",
                "orange",
            )
            self.root.after(0, self._set_status, "Error - OpenOCD not found", "red")
        except Exception as e:
            self._log(f"[ERROR] {e}", "red")
            self.root.after(0, self._set_status, f"Error - {e}", "red")
        finally:
            self.is_flashing = False
            self.root.after(0, self.flash_btn.configure, {"state": "normal"})

    # ── OpenOCD Install ──────────────────────────────────────────────

    def _on_install(self):
        if self.is_flashing:
            return
        self.install_btn.configure(state="disabled")
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")

        self._log("=" * 44, "blue")
        self._log(" Installing OpenOCD (bundled)...", "blue")
        self._log("=" * 44, "blue")
        self._log("")

        thread = threading.Thread(target=self._run_install, daemon=True)
        thread.start()

    def _run_install(self):
        try:
            url = get_openocd_download_url()
            self._log(f"[INFO] Platform: {SYSTEM}", "cyan")
            self._log(f"[INFO] Download URL: {url}", "cyan")
            self._log("")

            # Clean existing, ensure parent openocd/ exists
            openocd_parent = os.path.dirname(OPENOCD_OS_DIR)
            if os.path.isdir(OPENOCD_OS_DIR):
                shutil.rmtree(OPENOCD_OS_DIR)
            os.makedirs(OPENOCD_OS_DIR, exist_ok=True)

            # Download
            self._log("[INFO] Downloading OpenOCD...", "green")
            self.root.after(0, self._set_status, "Downloading OpenOCD...", "orange")

            def dl_progress(count, block_size, total_size):
                if total_size > 0:
                    percent = min(100, int(count * block_size * 100 / total_size))
                    self.root.after(
                        0,
                        self._set_status,
                        f"Downloading OpenOCD... {percent}%",
                        "orange",
                    )

            urllib.request.urlretrieve(url, OPENOCD_ARCHIVE, dl_progress)
            self._log("[INFO] Download complete!", "green")
            self.root.after(0, self._set_status, "Extracting OpenOCD...", "orange")

            # Extract
            self._log("[INFO] Extracting...", "green")
            extract_temp = os.path.join(SCRIPT_DIR, "openocd_temp")
            if os.path.isdir(extract_temp):
                shutil.rmtree(extract_temp)
            os.makedirs(extract_temp, exist_ok=True)

            if url.endswith(".zip"):
                with zipfile.ZipFile(OPENOCD_ARCHIVE, "r") as zf:
                    zf.extractall(extract_temp)
            elif url.endswith(".tar.gz"):
                with tarfile.open(OPENOCD_ARCHIVE, "r:gz") as tf:
                    tf.extractall(extract_temp)

            self._log("[OK] Extraction complete", "green")
            os.remove(OPENOCD_ARCHIVE)

            # Find the xPack root and move files
            items = os.listdir(extract_temp)
            xpack_root = extract_temp
            if len(items) == 1 and os.path.isdir(os.path.join(extract_temp, items[0])):
                xpack_root = os.path.join(extract_temp, items[0])

            # Find bin/ directory
            bin_dir = os.path.join(xpack_root, "bin")
            if not os.path.isdir(bin_dir):
                # Search recursively
                for root, dirs, files in os.walk(xpack_root):
                    if EXE_NAME in files:
                        bin_dir = root
                        xpack_root = os.path.dirname(root)
                        break

            # Copy executable and DLLs/SOs
            if os.path.isdir(bin_dir):
                for item in os.listdir(bin_dir):
                    src = os.path.join(bin_dir, item)
                    dst = os.path.join(OPENOCD_OS_DIR, item)
                    if os.path.isfile(src):
                        shutil.copy2(src, dst)
                self._log(f"[OK] {EXE_NAME} + libraries copied", "green")

            # Copy scripts
            scripts_src = os.path.join(xpack_root, "openocd", "scripts")
            if not os.path.isdir(scripts_src):
                # Also check directly under xpack_root
                scripts_src = os.path.join(xpack_root, "scripts")
            if os.path.isdir(scripts_src):
                dst_scripts = os.path.join(OPENOCD_OS_DIR, "scripts")
                shutil.copytree(scripts_src, dst_scripts)
                self._log("[OK] Scripts copied (interface/, target/, etc.)", "green")

            # Cleanup
            shutil.rmtree(extract_temp, ignore_errors=True)
            if os.path.isfile(OPENOCD_ARCHIVE):
                os.remove(OPENOCD_ARCHIVE)

            # Verify
            if get_openocd_path():
                self._log("")
                self._log("=" * 44, "green")
                self._log(" OpenOCD installed successfully!", "green")
                self._log("=" * 44, "green")
                self._log("")
                self._log(f"  location: {OPENOCD_OS_DIR}", "green")
                self.root.after(0, self._set_status, "Ready (bundled OpenOCD)", "green")
            else:
                self._log("[WARN] openocd not found after extraction", "orange")
                self._log(
                    f"[HINT] Manually copy openocd into: {OPENOCD_OS_DIR}", "orange"
                )

        except Exception as e:
            self._log(f"[ERROR] Download/install failed: {e}", "red")
            self._log("[HINT] Manually download OpenOCD (xPack build) from:", "orange")
            self._log(
                "       https://github.com/xpack-dev-tools/openocd-xpack/releases",
                "orange",
            )
            self._log(f"[HINT] Extract and copy files into: {OPENOCD_DIR}", "orange")
            self.root.after(
                0, self._set_status, "OpenOCD download failed - see log", "red"
            )
        finally:
            self.root.after(0, self.install_btn.configure, {"state": "normal"})

    # ── Startup ──────────────────────────────────────────────────────

    def _on_startup(self):
        self.root.after(100, self._startup_checks)

    def _startup_checks(self):
        if get_openocd_path():
            self._set_status("Ready (bundled OpenOCD)", "green")
            self._log("[OK] Using bundled OpenOCD", "green")
        else:
            self._log("[INFO] OpenOCD not found. Auto-downloading...", "orange")
            self._log("[INFO] This is a one-time setup.", "orange")
            self.install_btn.configure(state="disabled")
            thread = threading.Thread(target=self._auto_install_startup, daemon=True)
            thread.start()

    def _auto_install_startup(self):
        self._run_install()
        if not get_openocd_path():
            self._log("")
            self._log("[HINT] If download fails, manually install:", "orange")
            self._log(
                "       Download: https://github.com/xpack-dev-tools/openocd-xpack/releases",
                "orange",
            )
            self._log(f"       Extract and copy into: {OPENOCD_OS_DIR}", "orange")
            self._log(
                "       Make sure 'openocd' (or openocd.exe) and 'scripts/' folder exist.",
                "orange",
            )
            self.root.after(
                0, self._set_status, "OpenOCD download failed - see log", "red"
            )
        self.root.after(0, self.install_btn.configure, {"state": "normal"})

    # ── Launch ───────────────────────────────────────────────────────

    def run(self):
        self.root.mainloop()


# ── Entry Point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = FlashGUI()
    app.run()
