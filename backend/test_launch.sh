#!/bin/bash
# Check Edge process names
echo "=== ps comm ==="
ps -eo pid,comm | grep -iE 'edge|msedge' | head -5
echo "=== pgrep -x msedge ==="
pgrep -x msedge 2>/dev/null | wc -l
echo "=== pgrep -f msedge ==="
pgrep -f msedge 2>/dev/null | wc -l
echo "=== pgrep -af msedge | head ==="
pgrep -af msedge 2>/dev/null | head -3
echo "=== cat comm of first ==="
FIRST_PID=$(pgrep -f msedge | head -1)
cat /proc/$FIRST_PID/comm 2>/dev/null
echo ""
echo "=== Edge windows ==="
DISPLAY=:99 wmctrl -l 2>/dev/null | grep -i edge
