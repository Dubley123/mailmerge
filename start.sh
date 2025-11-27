#!/bin/bash
# MailMerge 项目启动脚本

# 进入项目目录
cd "$(dirname "$0")"

# 激活虚拟环境
echo "🔧 激活虚拟环境..."
echo ""
source .venv/bin/activate

# 启动服务
echo "🚀 启动 MailMerge 系统..."
echo "  📍 前端地址: http://localhost:8000"
echo "  📍 API文档: http://localhost:8000/docs"
echo "  📍 按 Ctrl+C 停止服务"
echo ""

if [ "$#" -gt 0 ]; then
    # Forward all provided args to app.py. Supports --reset, --set-default, or both.
    python app.py "$@"
else
    python app.py
fi
