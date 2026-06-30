#!/usr/bin/env bash
# J.A.R.V.I.S. Relay Agent — macOS/Linux Launcher
# Connects your device to the HF Space backend for desktop actions

set -e

echo "========================================"
echo "  J.A.R.V.I.S. Relay Agent — $(uname -s)"
echo "========================================"
echo ""

PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON="$cmd"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "[ERROR] Python not found. Install Python 3.12+ from https://python.org"
    exit 1
fi

# Install Playwright if needed
if ! $PYTHON -c "import playwright" 2>/dev/null; then
    echo "[SETUP] Installing Playwright..."
    $PYTHON -m pip install playwright
    $PYTHON -m playwright install chromium 2>/dev/null || true
fi

echo "[RELAY] Starting agent..."
echo "[RELAY] Server: https://dgfhgjhj-jarvis-ai-brain.hf.space"
echo "[RELAY] User ID: local"
echo ""
echo "Commands will be processed on this computer."
echo "Press Ctrl+C to stop the agent."
echo ""

$PYTHON relay_agent.py --user local
