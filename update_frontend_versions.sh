#!/bin/bash
# 手动更新前端静态文件版本号的快捷脚本

cd "$(dirname "$0")"

echo "📦 更新前端资源版本号（基于文件哈希）..."
python3 frontend/update_versions.py
echo ""
echo "✅ 完成！可以刷新浏览器查看最新版本"
