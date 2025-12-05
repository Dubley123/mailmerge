#!/bin/bash
# MailMerge Startup Script

# Change to project directory
cd "$(dirname "$0")"

# 0. Print Banner (Always output first)
echo "🚀 Starting MailMerge System..."
echo "  📍 Frontend: http://localhost:8000"
echo "  📍 API Docs: http://localhost:8000/docs"
echo ""

# Parse arguments
BACKEND=0
ARGS=()
for arg in "$@"; do
    if [ "$arg" = "--backend" ]; then
        BACKEND=1
    else
        ARGS+=("$arg")
    fi
done

# Activate Virtual Environment
source .venv/bin/activate

# 1. Backend Mode
if [ "$BACKEND" -eq 1 ]; then
    # Ensure log directory exists
    LOG_DIR="$(pwd)/logs"
    mkdir -p "$LOG_DIR"
    LOG_FILE="$LOG_DIR/service.log"
    PID_FILE="$LOG_DIR/service.pid"

    # Run update_versions (redirect to log)
    python3 frontend/update_versions.py >> "$LOG_FILE" 2>&1

    # Run app in background (redirect to log)
    nohup python app.py "${ARGS[@]}" >> "$LOG_FILE" 2>&1 &
    PID=$!
    echo $PID > "$PID_FILE"
    
    # Output status to terminal
    echo "✅ Service started in background (PID: $PID)."
    echo "📄 Log file: $LOG_FILE"

else
    # 2. Foreground Mode (Direct output)
    python3 frontend/update_versions.py
    python app.py "${ARGS[@]}"
fi
