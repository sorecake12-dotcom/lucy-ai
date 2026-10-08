#!/usr/bin/env bash
# ==============================================================================
# LUCY AI Assistant — Launcher for Linux & macOS
# ==============================================================================
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# Locate Python 3.11+
if command -v python3 >/dev/null 2>&1; then
    PY="python3"
elif command -v python >/dev/null 2>&1; then
    PY="python"
else
    echo "[ERROR] Python 3 is required to run LUCY." >&2
    echo "Please install Python 3.11 or newer." >&2
    exit 1
fi

# Check Python version >= 3.11
"$PY" -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)" 2>/dev/null || {
    echo "[ERROR] LUCY requires Python 3.11 or newer (detected $("$PY" --version))." >&2
    exit 1
}

# Run main.py
exec "$PY" main.py "$@"
