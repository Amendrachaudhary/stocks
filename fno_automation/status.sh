#!/bin/bash
# ==============================================================================
# FNO Automation: Service Status & Log Monitor
# ==============================================================================

DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="$DIR/logs/fno_automation.log"

echo "============================================================"
echo "📊 FNO Automation Service Status"
echo "============================================================"

PID_LIST=$(pgrep -f "fno_automation/main.py")

if [ -n "$PID_LIST" ]; then
    echo "🟢 Status: ACTIVE & RUNNING"
    echo "   PIDs: $(echo $PID_LIST | tr '\n' ' ')"
    MAIN_PID=$(pgrep -f "python.*fno_automation/main.py" | head -n 1)
    if [ -z "$MAIN_PID" ]; then
        MAIN_PID=$(echo "$PID_LIST" | head -n 1)
    fi
    ps -p "$MAIN_PID" -o pid,%cpu,%mem,time,command | tail -n 1
else
    echo "🔴 Status: STOPPED (No active process)"
fi

echo ""
echo "=== Recent Logs (Last 15 lines) ==="
if [ -f "$LOG_FILE" ]; then
    tail -n 15 "$LOG_FILE"
else
    echo "No log file found at $LOG_FILE"
fi
echo "============================================================"
