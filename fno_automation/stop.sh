#!/bin/bash
# ==============================================================================
# FNO Automation: Service Stop Script
# ==============================================================================

PID=$(pgrep -f "fno_automation/main.py")

if [ -n "$PID" ]; then
    echo "Stopping FNO Automation (PID: $PID)..."
    kill $PID
    sleep 2
    if ps -p $PID > /dev/null 2>&1; then
        kill -9 $PID 2>/dev/null
    fi
    echo "✅ Process stopped."
else
    echo "⚪ No active FNO Automation process detected."
fi
