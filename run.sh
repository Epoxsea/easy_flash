#!/usr/bin/env bash
#
# STM32 EASY FLASH Launcher  (macOS / Linux / WSL)
# =================================================
# Tries Python GUI first, falls back to detailed help.
# Completely self-contained — never touches system PATH or global environment.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "========================================"
echo " STM32 EASY FLASH Launcher"
echo "========================================"
echo ""

# ── Find Python 3 (macOS/BSD compatible — no GNU grep needed) ──────────
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" --version 2>&1 | grep -E 'Python 3\.' || true)
        if [ -n "$ver" ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

# ── No Python 3 at all? ────────────────────────────────────────────────
if [ -z "$PYTHON" ]; then
    echo "[ERROR] Python 3 is required but not found on your system."
    echo ""
    echo "  This launcher is for running from source (development)."
    echo "  End users: download the prebuilt zip for your OS from the"
    echo "  GitHub Releases page instead - it needs no Python at all."
    echo ""
    echo "  Install Python 3:"
    echo ""
    echo "    macOS:  brew install python"
    echo "    Ubuntu: sudo apt install python3 python3-tk"
    echo "    Fedora: sudo dnf install python3 python3-tkinter"
    echo "    Any OS: https://www.python.org/downloads/"
    echo ""
    echo "  Then re-run this script."
    echo ""
    read -rp "Press Enter to exit..."
    exit 1
fi

echo "[INFO] Using: $($PYTHON --version 2>&1)"

# ── Pick GUI or CLI mode ────────────────────────────────────────────────
if [ "${1:-}" = "--cli" ]; then
    # CLI mode: pass remaining args to flash.py
    shift
    "$PYTHON" "$SCRIPT_DIR/flash.py" "$@"
    EXIT_CODE=$?
else
    # GUI mode: try to launch, catch tkinter errors gracefully
    "$PYTHON" "$SCRIPT_DIR/flash_gui.py"
    EXIT_CODE=$?
fi

# ── Handle errors ───────────────────────────────────────────────────────
if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "========================================"
    echo " Something went wrong."
    echo "========================================"
    echo ""

    # Check if it's a tkinter issue
    if ! "$PYTHON" -c "import tkinter" 2>/dev/null; then
        echo "[HELP] Python tkinter module is missing."
        echo ""
        echo "  Install it:"
        echo ""
        echo "    macOS:  brew install python-tk"
        echo "    Ubuntu: sudo apt install python3-tk"
        echo "    Fedora: sudo dnf install python3-tkinter"
        echo ""
    fi

    echo "  Options:"
    echo "    1. Install Python 3 from https://www.python.org/downloads/"
    echo "    2. Run CLI instead:  ./run.sh --cli <path/to/firmware.hex>"
    echo "    3. Run directly:     python3 flash_gui.py"
    echo ""
    read -rp "Press Enter to exit..."
    exit $EXIT_CODE
fi
