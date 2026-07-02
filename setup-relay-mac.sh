#!/usr/bin/env bash
# J.A.R.V.I.S. Relay Agent — macOS auto-installer
# Installs the relay as a LaunchAgent so it runs silently in the background forever.

set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_SRC="$DIR/com.jarvis.relay.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.jarvis.relay.plist"

if [ ! -f "$PLIST_SRC" ]; then
    echo "[ERROR] com.jarvis.relay.plist not found in $DIR"
    exit 1
fi

# Fix the working directory in the plist to match this location
sed "s|/Users/shaurjeshbasu/Downloads/HACK IN|$DIR|g" "$PLIST_SRC" > "$PLIST_DST"

# Unload if already loaded
launchctl unload "$PLIST_DST" 2>/dev/null || true

# Load the agent
launchctl load "$PLIST_DST"

echo "✅ J.A.R.V.I.S. Relay Agent installed as a background service."
echo "   It will start automatically on login and stay running."
echo "   Logs: /tmp/jarvis-relay.log"
echo "   Stop: launchctl unload $PLIST_DST"
echo ""
echo "Test it now by saying 'lock my PC' or 'open spotify' in the app."
