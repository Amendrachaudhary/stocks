#!/bin/bash
# ==============================================================================
# FNO Automation: 24/7 Live Daemon Launcher with Caffeinate & Log Rotation
# ==============================================================================

DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$DIR/../.venv/bin/python"
LOG_FILE="$DIR/logs/fno_automation.log"

echo "============================================================"
echo "🚀 Starting FNO Automation Engine (Live Production Mode)"
echo "============================================================"

# Check if an instance is already running
RUNNING_PID=$(pgrep -f "fno_automation/main.py")
if [ -n "$RUNNING_PID" ]; then
    echo "⚠️ Active process already detected (PID: $RUNNING_PID)."
    echo "Stopping existing instance..."
    kill $RUNNING_PID 2>/dev/null
    sleep 2
fi

# Ensure logs directory exists
mkdir -p "$DIR/logs"

# Launch in background with caffeinate to prevent sleep
nohup caffeinate -sim "$PYTHON" "$DIR/main.py" >> "$LOG_FILE" 2>&1 &
NEW_PID=$!

sleep 2

if ps -p $NEW_PID > /dev/null 2>&1; then
    echo "🟢 System is LIVE in the background!"
    echo "   PID: $NEW_PID"
    echo "   Log: $LOG_FILE"
    echo "============================================================"
else
    echo "❌ Failed to launch. Check log file at $LOG_FILE."
    exit 1
fi
