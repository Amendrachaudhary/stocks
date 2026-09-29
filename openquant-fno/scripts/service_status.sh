#!/bin/bash
# ==============================================================================
# OpenQuant-FNO: 24/7 Service Status & Live Logs Inspector
# ==============================================================================

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "============================================================"
echo "📊 OpenQuant-FNO Background Service Status"
echo "============================================================"

# 1. Check launchctl registration
if launchctl list | grep -q "com.openquant.fno"; then
    STATUS_LINE=$(launchctl list | grep "com.openquant.fno")
    PID=$(echo "$STATUS_LINE" | awk '{print $1}')
    EXIT_CODE=$(echo "$STATUS_LINE" | awk '{print $2}')
    echo "🟢 launchd Status: REGISTERED"
    echo "   PID: ${PID:--}"
    echo "   Last Exit Code: $EXIT_CODE"
else
    echo "⚪ launchd Status: NOT RUNNING"
fi

# 2. Check actual running python process
RUNNING_PID=$(pgrep -f "openquant-fno/main.py")
if [ -n "$RUNNING_PID" ]; then
    echo "🟢 Active Process: Running (PID: $RUNNING_PID)"
    # Check if network connection to Telegram is open
    SOCK=$(lsof -i -a -p "$RUNNING_PID" 2>/dev/null | grep -i "established")
    if [ -n "$SOCK" ]; then
        echo "⚡ Telegram Connection: ESTABLISHED & LISTENING"
    fi
else
    echo "🔴 Active Process: Not detected"
fi

echo ""
echo "=== Recent Logs (Last 15 lines) ==="
if [ -f "$PROJECT_DIR/logs/openquant_stdout.log" ]; then
    tail -n 15 "$PROJECT_DIR/logs/openquant_stdout.log"
else
    echo "No log file found yet."
fi

echo ""
echo "=== Recent Errors (Last 10 lines) ==="
if [ -f "$PROJECT_DIR/logs/openquant_stderr.log" ]; then
    tail -n 10 "$PROJECT_DIR/logs/openquant_stderr.log"
else
    echo "No errors logged."
fi
