#!/bin/bash
# JARVIS WSL Workspace Setup
# Installs all dependencies for the isolated workspace backend.
# Run this inside WSL2: bash setup_wsl_workspace.sh

set -e

echo "╔══════════════════════════════════════════╗"
echo "║  JARVIS WSL Workspace Setup              ║"
echo "╚══════════════════════════════════════════╝"

# Update package list
echo "[1/6] Updating package list..."
sudo apt-get update -qq

# Install display server and input tools
echo "[2/6] Installing Xvfb, xdotool, scrot, wmctrl..."
sudo apt-get install -y -qq \
    xvfb \
    xdotool \
    scrot \
    wmctrl \
    imagemagick \
    x11-utils \
    x11-xserver-utils \
    python3-xlib

# Install browser
echo "[3/6] Installing Google Chrome..."
if ! command -v google-chrome-stable &>/dev/null; then
    wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
    sudo apt-get update -qq
    sudo apt-get install -y -qq google-chrome-stable
else
    echo "  Chrome already installed"
fi

# Install Python dependencies
echo "[4/6] Installing Python packages..."
pip3 install --quiet --upgrade \
    pyautogui \
    mss \
    Pillow \
    numpy \
    python-xlib \
    pynput

# Install development tools
echo "[5/6] Installing dev tools..."
sudo apt-get install -y -qq \
    git \
    curl \
    wget \
    build-essential \
    python3-dev \
    python3-pip \
    nodejs \
    npm

# Create workspace directories
echo "[6/6] Creating workspace structure..."
mkdir -p ~/.jarvis/workspaces
mkdir -p ~/.jarvis/screenshots

# Test Xvfb
echo ""
echo "Testing Xvfb..."
Xvfb :99 -screen 0 1920x1080x24 -ac &
XVFB_PID=$!
sleep 1

if DISPLAY=:99 xdpyinfo >/dev/null 2>&1; then
    echo "  ✓ Xvfb working on :99"
else
    echo "  ✗ Xvfb test failed"
fi

kill $XVFB_PID 2>/dev/null || true

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  Setup complete!                         ║"
echo "║                                          ║"
echo "║  Required tools installed:               ║"
echo "║    ✓ Xvfb (virtual display)             ║"
echo "║    ✓ xdotool (input injection)          ║"
echo "║    ✓ scrot (screenshots)                ║"
echo "║    ✓ wmctrl (window management)         ║"
echo "║    ✓ Google Chrome                       ║"
echo "║    ✓ Python packages                     ║"
echo "║                                          ║"
echo "║  JARVIS can now create isolated          ║"
echo "║  workspaces inside WSL.                  ║"
echo "╚══════════════════════════════════════════╝"
