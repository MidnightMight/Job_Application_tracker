#!/usr/bin/env bash
# launch.sh — One-command launcher for Job Application Tracker
# Supports: Linux · macOS · Unix (FreeBSD, OpenBSD, NetBSD, Solaris …)
# Usage:  bash launch.sh
#    or:  chmod +x launch.sh && ./launch.sh

set -e

# ── Resolve the directory that contains this script ─────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="$SCRIPT_DIR/venv"
PORT="${PORT:-5000}"

# ── Detect operating system ──────────────────────────────────────────────────
OS="$(uname -s 2>/dev/null || echo Unknown)"
case "$OS" in
    Linux*)   PLATFORM="Linux" ;;
    Darwin*)  PLATFORM="macOS" ;;
    FreeBSD*) PLATFORM="FreeBSD" ;;
    OpenBSD*) PLATFORM="OpenBSD" ;;
    NetBSD*)  PLATFORM="NetBSD" ;;
    SunOS*)   PLATFORM="Solaris" ;;
    CYGWIN*|MINGW*|MSYS*) PLATFORM="Windows-Unix" ;;
    *)        PLATFORM="Unix" ;;
esac

echo "[launcher] Detected platform: $PLATFORM"

# ── Find a usable Python 3 interpreter ──────────────────────────────────────
PYTHON=""
for candidate in python3 python3.13 python3.12 python3.11 python3.10 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        # Verify it is actually Python 3.
        version=$("$candidate" -c "import sys; print(sys.version_info.major)" 2>/dev/null || echo 0)
        if [ "$version" = "3" ]; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo ""
    echo "[ERROR] Python 3 was not found on your PATH."
    echo ""
    case "$PLATFORM" in
        Linux)
            echo "  Install it with your package manager, e.g.:"
            echo "    sudo apt install python3 python3-venv   # Debian / Ubuntu"
            echo "    sudo dnf install python3                 # Fedora / RHEL"
            echo "    sudo pacman -S python                    # Arch"
            ;;
        macOS)
            echo "  Install it via Homebrew:  brew install python"
            echo "  Or download from:         https://www.python.org/downloads/"
            ;;
        FreeBSD|OpenBSD|NetBSD)
            echo "  Install it with:  pkg install python3   (FreeBSD)"
            echo "                or: pkg_add python3       (OpenBSD / NetBSD)"
            ;;
        *)
            echo "  Download Python 3.10+ from https://www.python.org/downloads/"
            ;;
    esac
    echo ""
    exit 1
fi

echo "[launcher] Using Python: $($PYTHON --version)"

# ── Create virtual environment if it doesn't exist ──────────────────────────
if [ ! -d "$VENV_DIR" ]; then
    echo "[launcher] Creating virtual environment in ./venv ..."
    "$PYTHON" -m venv "$VENV_DIR" || {
        echo ""
        echo "[ERROR] Failed to create virtual environment."
        case "$PLATFORM" in
            Linux)
                echo "  You may need the venv module:"
                echo "    sudo apt install python3-venv   # Debian / Ubuntu"
                echo "    sudo dnf install python3        # Fedora / RHEL"
                ;;
            macOS)
                echo "  Try: brew install python   (Homebrew Python includes venv)"
                ;;
        esac
        echo ""
        exit 1
    }
fi

# ── Activate the virtual environment ────────────────────────────────────────
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# ── Install / upgrade dependencies ──────────────────────────────────────────
echo "[launcher] Installing / verifying dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

# ── Open browser after a short delay (best-effort, non-fatal) ───────────────
_open_browser() {
    sleep 2
    URL="http://localhost:$PORT"
    case "$PLATFORM" in
        macOS)
            open "$URL" 2>/dev/null || true
            ;;
        Linux)
            # Try common Linux browser launchers in order of preference.
            for opener in xdg-open gnome-open kde-open sensible-browser; do
                if command -v "$opener" >/dev/null 2>&1; then
                    "$opener" "$URL" 2>/dev/null || true
                    break
                fi
            done
            ;;
        FreeBSD|OpenBSD|NetBSD)
            for opener in xdg-open firefox chromium; do
                if command -v "$opener" >/dev/null 2>&1; then
                    "$opener" "$URL" 2>/dev/null || true
                    break
                fi
            done
            ;;
        Windows-Unix)
            # Git Bash / Cygwin / MSYS2 on Windows.
            start "$URL" 2>/dev/null || true
            ;;
    esac
}

# Only try to open the browser if we have a display environment.
if [ -n "$DISPLAY" ] || [ -n "$WAYLAND_DISPLAY" ] || [ "$PLATFORM" = "macOS" ] || [ "$PLATFORM" = "Windows-Unix" ]; then
    _open_browser &
fi

# ── Start the server ─────────────────────────────────────────────────────────
echo "[launcher] Starting Job Tracker at http://localhost:$PORT"
echo "[launcher] Press Ctrl+C to stop."
echo ""
exec python app.py

