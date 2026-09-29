#!/bin/bash
# ==============================================================================
# OpenQuant-FNO: Stop 24/7 macOS Background Service
# ==============================================================================

PLIST_NAME="com.openquant.fno.plist"
DEST_PLIST="$HOME/Library/LaunchAgents/$PLIST_NAME"

echo "=== Stopping OpenQuant-FNO Background Service ==="
if [ -f "$DEST_PLIST" ]; then
    launchctl unload "$DEST_PLIST" 2>/dev/null
    echo "✅ Service unloaded from launchd."
else
    echo "ℹ️ LaunchAgent plist not found at $DEST_PLIST."
fi

# Kill any lingering process
RUNNING_PIDS=$(pgrep -f "openquant-fno/main.py")
if [ -n "$RUNNING_PIDS" ]; then
    kill $RUNNING_PIDS 2>/dev/null
    echo "🛑 Terminated background process (PID: $RUNNING_PIDS)."
fi

echo "OpenQuant-FNO service is STOPPED."
