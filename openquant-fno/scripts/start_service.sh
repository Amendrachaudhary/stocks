#!/bin/bash
# ==============================================================================
# OpenQuant-FNO: macOS 24/7 Background Service Launcher
# ==============================================================================

PLIST_NAME="com.openquant.fno.plist"
SRC_PLIST="$(cd "$(dirname "$0")/.." && pwd)/deploy/$PLIST_NAME"
DEST_PLIST="$HOME/Library/LaunchAgents/$PLIST_NAME"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== OpenQuant-FNO: 24/7 Service Setup ==="

# 1. Ensure logs directory exists
mkdir -p "$PROJECT_DIR/logs"

# 2. Check if a manual foreground process is already running
RUNNING_PIDS=$(pgrep -f "openquant-fno/main.py")
if [ -n "$RUNNING_PIDS" ]; then
    echo "⚠️ Existing OpenQuant process detected (PID: $RUNNING_PIDS)."
    echo "Stopping existing instance to avoid database session lock..."
    kill $RUNNING_PIDS 2>/dev/null
    sleep 2
fi

# 3. Copy plist into LaunchAgents
mkdir -p "$HOME/Library/LaunchAgents"
cp "$SRC_PLIST" "$DEST_PLIST"
echo "✅ Installed LaunchAgent to $DEST_PLIST"

# 4. Unload if already loaded, then load fresh
launchctl unload "$DEST_PLIST" 2>/dev/null
launchctl load "$DEST_PLIST"
echo "🚀 Loaded LaunchAgent into macOS launchd system."

sleep 2

# 5. Check status
if launchctl list | grep -q "com.openquant.fno"; then
    PID=$(launchctl list | grep "com.openquant.fno" | awk '{print $1}')
    echo "============================================================"
    echo "🎉 OpenQuant-FNO is now running 24/7 in the background!"
    echo "   PID: $PID"
    echo "   Logs: $PROJECT_DIR/logs/openquant_stdout.log"
    echo "   Auto-restarts whenever connected to internet: ACTIVE"
    echo "============================================================"
else
    echo "❌ Failed to register with launchd. Check logs."
fi
