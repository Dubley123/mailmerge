#!/bin/bash
# MailMerge 项目启动脚本

# 进入项目目录
cd "$(dirname "$0")"

# 激活虚拟环境
echo "🔧 激活虚拟环境..."
echo ""
source .venv/bin/activate

# 通用提示
echo "🚀 启动 MailMerge 系统..."
echo "  📍 前端地址: http://localhost:8000"
echo "  📍 API文档: http://localhost:8000/docs"
echo "  📍 按 Ctrl+C 停止服务（前台模式）"
echo ""

# 解析参数，支持 --backend（将其从转发参数中移除）
BACKEND=0
ARGS=()
for arg in "$@"; do
    if [ "$arg" = "--backend" ]; then
        BACKEND=1
    else
        ARGS+=("$arg")
    fi
done

if [ "$BACKEND" -eq 1 ]; then
    # 确保日志目录存在
    LOG_DIR="$(pwd)/logs"
    mkdir -p "$LOG_DIR"
    LOG_FILE="$LOG_DIR/service.log"
    PID_FILE="$LOG_DIR/service.pid"

    echo "启动后台模式，日志将写入: $LOG_FILE"

    # 使用 nohup 将进程置于后台并重定向输出
    nohup python app.py "${ARGS[@]}" > "$LOG_FILE" 2>&1 &
    PID=$!
    # 记录 PID 方便后续管理
    echo $PID > "$PID_FILE"
    echo "服务已在后台启动 (PID: $PID)。日志: $LOG_FILE"
    exit 0
else
    # 前台运行，直接转发剩余参数（若有）
    if [ ${#ARGS[@]} -gt 0 ]; then
        python app.py "${ARGS[@]}"
    else
        python app.py
    fi
fi
