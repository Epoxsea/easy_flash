#!/usr/bin/env python3
"""
STM32 EASY FLASH - Cross-platform GUI for flashing STM32 microcontrollers.

This application helps users flash .hex firmware files to STM32 boards using
ST-Link programmers. It provides an intuitive interface that's accessible to
non-developers while maintaining full functionality for experienced users.
"""

# Standard Python imports
import os
import queue
import subprocess
import sys
import threading
import json

# Import local modules - only functions that actually exist in openocd_bundle.py
from openocd_bundle import (
    bundle_dir,
    get_openocd_path,       # Returns path or None if not installed
    get_scripts_dir,        # Returns scripts directory or None
    install_openocd,        # Downloads + extracts OpenOCD
)

# The macOS standalone is frozen with python-build-standalone, which links
# Tcl/Tk statically into libpython with a TCL_LIBRARY baked in at build time.
# PyInstaller bundles the real Tcl/Tk data under <bundle>/_tcl_data and
# <bundle>/_tk_data, so point Tcl at them before importing tkinter.
if getattr(sys, "frozen", False):
    _bundle = bundle_dir()
    for _var, _path in (
        ("TCL_LIBRARY", os.path.join(_bundle, "_tcl_data")),
        ("TK_LIBRARY", os.path.join(_bundle, "_tk_data")),
    ):
        if os.path.exists(_path):
            os.environ.setdefault(_var, _path)

# Try to import tkinter
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext
    TK_AVAILABLE = True
except ImportError:
    TK_AVAILABLE = False

# Try to import ttkbootstrap for enhanced UI if available  
try:
    import ttkbootstrap as tb
    from ttkbootstrap.constants import *
    TTKBOOTSTRAP_AVAILABLE = True
except ImportError:
    TTKBOOTSTRAP_AVAILABLE = False

if not TK_AVAILABLE:
    print("No GUI available. Please install tkinter to use the GUI interface.")
    print("Alternatively, use the CLI: python flash.py <hex_file>")
    sys.exit(0)

# Default OpenOCD configs
DEFAULT_INTERFACE_CFG = "interface/stlink.cfg"
DEFAULT_TARGET_CFG = "target/stm32f1x.cfg"

# App install dir
SCRIPT_DIR = bundle_dir()
PROJECT_DIR = SCRIPT_DIR if getattr(sys, "frozen", False) else os.path.abspath(
    os.path.join(SCRIPT_DIR, "..")
)


# ── GUI Application ────────────────────────────────────────────────────────


class FlashGUI:
    def __init__(self):
        """Initialize the GUI application"""
        # Initialize main window
        try:
            if TTKBOOTSTRAP_AVAILABLE:
                self.root = tb.Window(themename="cosmo")
            else:
                self.root = tk.Tk()
            
            self.root.title("STM32 EASY FLASH")
            self.root.geometry("800x700")
            self.root.resizable(False, False)
            
            # Center window
            self.root.update_idletasks()
            w = self.root.winfo_width()
            h = self.root.winfo_height()
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            x = (sw - w) // 2
            y = (sh - h) // 2
            self.root.geometry(f"+{x}+{y}")

            # State variables
            self.interface_cfg = DEFAULT_INTERFACE_CFG
            self.target_cfg = DEFAULT_TARGET_CFG
            self.is_flashing = False
            self.settings_file = "easyflash.json"
            
            # UI elements queue
            self._ui_queue = queue.Queue()
            
            # Load existing settings if available
            self.load_settings()
            
            # Create the GUI elements
            if TTKBOOTSTRAP_AVAILABLE:
                self.create_widgets_enhanced()
            else:
                self.create_widgets_basic()
                
        except Exception as e:
            print(f"Error initializing GUI: {e}")
            print("Falling back to text mode")
            self.run_text_interface()

    def create_widgets_enhanced(self):
        """Create enhanced widgets with ttkbootstrap theming"""
        main_frame = tb.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Title frame  
        title_frame = tb.Frame(main_frame)
        title_frame.pack(fill="x", pady=(0, 15))
        
        title_label = tb.Label(
            title_frame, 
            text="STM32 EASY FLASH", 
            font=("Segoe UI", 20, "bold"),
            foreground="white",
            background="#0067c0"
        )
        title_label.pack(pady=10)
        
        # File selection section
        file_frame = tb.LabelFrame(main_frame, text="Firmware File", padding=10)
        file_frame.pack(fill="x", pady=(0, 15))
        
        hex_row = tb.Frame(file_frame)
        hex_row.pack(fill="x")
        
        self.hex_var = tb.StringVar()
        
        hex_label = tb.Label(hex_row, text="Hex file:")
        hex_label.pack(side="left", padx=(0, 10))
        
        self.hex_entry = tb.Entry(hex_row, textvariable=self.hex_var)
        self.hex_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        hex_btn = tb.Button(hex_row, text="Browse...", command=self.select_hex_file)
        hex_btn.pack(side="right")
        
        # Target selection section
        target_frame = tb.LabelFrame(main_frame, text="Target Board", padding=10)
        target_frame.pack(fill="x", pady=(0, 15))
        
        target_row = tb.Frame(target_frame) 
        target_row.pack(fill="x")
        
        self.target_var = tb.StringVar()
        
        target_label = tb.Label(target_row, text="Board:")
        target_label.pack(side="left", padx=(0, 10))
        
        self.target_dropdown = tb.Combobox(target_row, textvariable=self.target_var, state="readonly")
        self.target_dropdown.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        # Populate the dropdown with available targets from flasher module
        try:
            from flasher import list_targets
            targets = list_targets()
            target_labels = [label for label, _ in targets] 
            self.target_dropdown['values'] = target_labels
            
            if target_labels:
                self.target_var.set(target_labels[0])
                self.target_cfg = targets[0][1]
        except Exception as e:
            print(f"Error loading targets: {e}")
            self.target_dropdown['values'] = ["Generic STM32F1 Board"]
            self.target_var.set("Generic STM32F1 Board")
        
        # Status section
        status_frame = tb.LabelFrame(main_frame, text="Status", padding=10)
        status_frame.pack(fill="x", pady=(0, 15))
        
        self.status_label = tb.Label(status_frame, text="Ready to flash")
        self.status_label.pack(side="left")
        
        # Progress bar
        self.progress = tb.Progressbar(main_frame, mode='determinate')
        self.progress.pack(fill="x", pady=(10, 0), padx=20)
        self.progress.pack_forget()
        
        # Operation buttons
        button_frame = tb.Frame(main_frame)
        button_frame.pack(fill="x", pady=(10, 0))
        
        self.flash_btn = tb.Button(button_frame, text="Flash Firmware", command=self.start_flash, bootstyle="success")
        self.flash_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        self.cancel_btn = tb.Button(button_frame, text="Cancel", command=self.cancel_flash, bootstyle="danger")
        self.cancel_btn.pack(side="right", fill="x", expand=True, padx=(5, 0))
        self.cancel_btn.pack_forget()
        
        # Output log section
        log_frame = tb.LabelFrame(main_frame, text="Output Log", padding=10)
        log_frame.pack(fill="both", expand=True, pady=(10, 0))
        
        self.output = tb.ScrolledText(log_frame, height=10)
        self.output.pack(fill="both", expand=True)
        
        # Bottom buttons
        bottom_frame = tb.Frame(main_frame)
        bottom_frame.pack(fill="x", pady=(10, 0))
        
        self.reinstall_btn = tb.Button(bottom_frame, text="Reinstall OpenOCD", command=self.reinstall_openocd, bootstyle="warning")
        self.reinstall_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        try:
            self.theme_btn = tb.Button(bottom_frame, text="Toggle Theme", command=self.toggle_theme, bootstyle="secondary")  
            self.theme_btn.pack(side="right", fill="x", expand=True, padx=(5, 0))
        except:
            pass
        
        # Setup drag and drop
        try:
            self.root.drop_target_register(tk.DND_FILES)
            self.root.dnd_bind('<<Drop>>', self.on_drop_file)
        except Exception as e:
            print(f"Warning: Drag-and-drop not supported: {e}")
            
        # Auto-detect ST-Link connection on startup
        self.auto_detect_stlink()

    def create_widgets_basic(self):
        """Create basic widgets using pure tkinter"""
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        title_frame = tk.Frame(main_frame, bg="#0067c0", height=60)
        title_frame.pack(fill="x", pady=(0, 15))
        
        title_label = tk.Label(
            title_frame, 
            text="STM32 EASY FLASH", 
            font=("Arial", 20, "bold"),
            foreground="#ffffff",
            background="#0067c0"
        )
        title_label.pack(pady=10)
        
        file_frame = tk.LabelFrame(main_frame, text="Firmware File", padx=10, pady=10)
        file_frame.pack(fill="x", pady=(0, 15))
        
        hex_row = tk.Frame(file_frame)
        hex_row.pack(fill="x")
        
        self.hex_var = tk.StringVar()
        
        hex_label = tk.Label(hex_row, text="Hex file:")
        hex_label.pack(side="left", padx=(0, 10))
        
        self.hex_entry = tk.Entry(hex_row, textvariable=self.hex_var)
        self.hex_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        hex_btn = tk.Button(hex_row, text="Browse...", command=self.select_hex_file)
        hex_btn.pack(side="right")
        
        target_frame = tk.LabelFrame(main_frame, text="Target Board", padx=10, pady=10)
        target_frame.pack(fill="x", pady=(0, 15))
        
        target_row = tk.Frame(target_frame) 
        target_row.pack(fill="x")
        
        self.target_var = tk.StringVar()
        
        target_label = tk.Label(target_row, text="Board:")
        target_label.pack(side="left", padx=(0, 10))
        
        self.target_dropdown = tk.Combobox(target_row, textvariable=self.target_var, state="readonly")
        self.target_dropdown.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        self.target_dropdown['values'] = ["Generic STM32F1 Board"]
        self.target_var.set("Generic STM32F1 Board")
        
        status_frame = tk.LabelFrame(main_frame, text="Status", padx=10, pady=10)
        status_frame.pack(fill="x", pady=(0, 15))
        
        self.status_label = tk.Label(status_frame, text="Ready to flash")
        self.status_label.pack(side="left")
        
        button_frame = tk.Frame(main_frame)
        button_frame.pack(fill="x", pady=(10, 0))
        
        self.flash_btn = tk.Button(button_frame, text="Flash Firmware", command=self.start_flash)
        self.flash_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        self.cancel_btn = tk.Button(button_frame, text="Cancel", command=self.cancel_flash)
        self.cancel_btn.pack(side="right", fill="x", expand=True, padx=(5, 0))
        self.cancel_btn.pack_forget()
        
        log_frame = tk.LabelFrame(main_frame, text="Output Log", padx=10, pady=10)
        log_frame.pack(fill="both", expand=True, pady=(10, 0))
        
        self.output = scrolledtext.ScrolledText(log_frame, height=10)
        self.output.pack(fill="both", expand=True)
        
        bottom_frame = tk.Frame(main_frame)
        bottom_frame.pack(fill="x", pady=(10, 0))
        
        self.reinstall_btn = tk.Button(bottom_frame, text="Reinstall OpenOCD", command=self.reinstall_openocd)
        self.reinstall_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        try:
            self.root.drop_target_register(tk.DND_FILES)
            self.root.dnd_bind('<<Drop>>', self.on_drop_file)
        except Exception as e:
            print(f"Warning: Drag-and-drop not supported: {e}")
            
        self.auto_detect_stlink()

    def select_hex_file(self):
        """Allow user to select a hex file"""
        try:
            hex_path = filedialog.askopenfilename(
                title="Select Firmware File",
                filetypes=[("Hex files", "*.hex"), ("All files", "*.*")]
            )
            if hex_path:
                self.hex_var.set(hex_path)
        except Exception as e:
            print(f"Error selecting file: {e}")

    def on_drop_file(self, event):
        """Handle dropped files"""
        try:
            if event.data:
                files = event.data.split()
                if files and files[0].endswith('.hex'):
                    self.hex_var.set(files[0])
        except Exception as e:
            print(f"Error handling drop: {e}")

    def set_status(self, message, color="blue"):
        """Set status text"""
        try:
            self.status_label.config(text=message)
        except Exception as e:
            print(f"Failed to update status: {e}")

    def start_flash(self):
        """Start the flashing operation"""
        hex_path = self.hex_var.get().strip()
        
        if not hex_path:
            messagebox.showerror("Error", "Please select a firmware file")
            return
            
        if not os.path.exists(hex_path):
            messagebox.showerror("Error", f"File not found: {hex_path}")
            return
            
        # Update button state
        self.set_status("Starting flash operation...")
        self.flash_btn.pack_forget()
        self.cancel_btn.pack(side="right", fill="x", expand=True, padx=(5, 0))
        self.cancel_btn.config(state="normal")
        self.progress.pack(fill="x", pady=(10, 0), padx=20)
        self.progress["value"] = 0
        
        # Start flashing in a separate thread
        self.is_flashing = True
        flash_thread = threading.Thread(target=self.flash_worker, args=(hex_path,))
        flash_thread.daemon = True
        flash_thread.start()

    def cancel_flash(self):
        """Cancel the flashing operation"""
        if self.is_flashing:
            self.set_status("Cancelling...")

    def flash_worker(self, hex_path):
        """Worker function to perform flashing in background thread"""
        try:
            self.ui_queue_put(lambda: self.set_status("Detecting programmer..."))
            openocd_path = get_openocd_path()
            
            if not openocd_path:
                self.ui_queue_put(lambda: self.set_status("OpenOCD not installed. Please click 'Reinstall OpenOCD' first."))
                return
            
            # Try to detect ST-Link
            from flasher import detect_programmer
            detected, lines = detect_programmer(openocd_path, self.interface_cfg)
            
            if not detected:
                self.ui_queue_put(lambda: self.set_status("No ST-Link found. Please connect your programmer."))
                raise Exception("ST-Link not detected")
            
            self.ui_queue_put(lambda: self.set_status("Flashing firmware..."))
            
            from flasher import flash, describe_failure
            
            self.ui_queue_put(lambda: self.output.delete('1.0', tk.END))
            self.ui_queue_put(lambda: self.output.insert(tk.END, "Starting flash process...\n"))
            
            def log_line(line):
                if not line.endswith('\n'):
                    line += '\n'
                self.ui_queue_put(lambda: self.output.insert(tk.END, line))
                self.ui_queue_put(lambda: self.output.see(tk.END))
                
            rc = flash(
                openocd_path, 
                self.interface_cfg,
                self.target_cfg, 
                hex_path, 
                log=log_line
            )
            
            if rc == 0:
                success_msg = f"Successfully flashed {hex_path} to STM32 board!"
                self.ui_queue_put(lambda: self.set_status(success_msg))
                self.ui_queue_put(lambda: self.output.insert(tk.END, "\n" + success_msg))
                self.save_settings()
            else:
                hints = describe_failure(rc)
                error_msg = f"Flashing failed with error code {rc}"
                self.ui_queue_put(lambda: self.set_status(error_msg))
                self.ui_queue_put(lambda: self.output.insert(tk.END, "\n" + error_msg))
                if hints:
                    for hint in hints:
                        self.ui_queue_put(lambda: self.output.insert(tk.END, f"\nHint: {hint}"))
            
        except Exception as e:
            error_msg = f"Error during flash operation: {str(e)}"
            self.ui_queue_put(lambda: self.set_status(error_msg))
            self.ui_queue_put(lambda: self.output.insert(tk.END, "\n" + error_msg))
            
        finally:
            self.ui_queue_put(lambda: 
                self.flash_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))
            )
            self.ui_queue_put(lambda: self.cancel_btn.pack_forget())
            self.ui_queue_put(lambda: self.progress.pack_forget())
            self.ui_queue_put(lambda: self.set_status("Ready to flash"))
            self.is_flashing = False

    def auto_detect_stlink(self):
        """Detect ST-Link connection"""
        try:
            openocd_path = get_openocd_path()
            
            if not openocd_path:
                self.ui_queue_put(lambda: self.set_status("OpenOCD not installed - click 'Reinstall OpenOCD'"))
                return
                
            from flasher import detect_programmer
            detected, lines = detect_programmer(openocd_path, self.interface_cfg)
            
            if detected:
                self.ui_queue_put(lambda: self.set_status("ST-Link detected"))
            else:
                self.ui_queue_put(lambda: self.set_status("ST-Link not detected - please connect your programmer"))
        except Exception as e:
            self.ui_queue_put(lambda: self.set_status(f"Detection error: {str(e)}"))

    def reinstall_openocd(self):
        """Reinstall OpenOCD"""
        try:
            install_openocd()
            messagebox.showinfo("Success", "OpenOCD reinstalled successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to reinstall OpenOCD: {str(e)}")

    def save_settings(self):
        """Save current settings to JSON"""
        try:
            settings = {
                'hex_path': self.hex_var.get(),
                'target_cfg': self.target_cfg,
                'interface_cfg': self.interface_cfg
            }
            
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f)
                
        except Exception as e:
            print(f"Failed to save settings: {e}")

    def load_settings(self):
        """Load saved settings from JSON"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    if 'hex_path' in settings:
                        self.hex_var.set(settings['hex_path'])
        except Exception as e:
            print(f"Failed to load settings: {e}")

    def toggle_theme(self):
        """Toggle between themes"""
        try:
            if hasattr(self.root, 'style'):
                current_theme = self.root.style.theme_use()
                if current_theme == "cosmo":
                    self.root.style.theme_use("darkly")
                else:
                    self.root.style.theme_use("cosmo")
        except Exception as e:
            print(f"Failed to toggle theme: {e}")

    def ui_queue_put(self, func):
        """Safely queue UI updates"""
        self._ui_queue.put(func)

    def process_ui_queue(self):
        """Process queued UI updates"""
        while not self._ui_queue.empty():
            try:
                func = self._ui_queue.get_nowait()
                func()
            except queue.Empty:
                break
        self.root.after(100, self.process_ui_queue)

    def run(self):
        """Run the GUI application"""
        if TTKBOOTSTRAP_AVAILABLE:
            self.root.after(100, self.process_ui_queue)
        
        try:
            self.root.mainloop()
        except Exception as e:
            print(f"Error running mainloop: {e}")

    def run_text_interface(self):
        """Fallback to text-based interface"""
        print("Starting STM32 EASY FLASH (Text Interface)")
        print("Please use command-line interface or install tkinter for GUI support")

        while True:
            try:
                cmd = input("\nCommands: flash, detect, help, quit\n> ").strip().lower()
                if cmd == "quit":
                    break
                elif cmd == "help":
                    print("Supported commands:")
                    print("- flash <hex_file>: Flash a firmware file")
                    print("- detect: Check ST-Link connection")
                    print("- help: Show this help")
                    print("- quit: Exit the application")
                elif cmd == "detect":
                    print("Auto-detection not available in text mode.")
                elif cmd.startswith("flash"):
                    print("Flash command not available in text mode.")
                else:
                    print(f"Unknown command: {cmd}")
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"Error processing command: {e}")


# ── Entry Point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        app = FlashGUI()
        app.run()
    except Exception as e:
        print(f"Application error: {e}")
        try:
            app.run_text_interface()
        except Exception as e2:
            print(f"Failed to run text interface: {e2}")
            sys.exit(1)