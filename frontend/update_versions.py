#!/usr/bin/env python3
"""
自动更新前端静态文件版本号
使用文件内容的MD5哈希值作为版本号，确保文件变更时自动更新缓存
"""

import hashlib
import re
from pathlib import Path

# 配置
FRONTEND_DIR = Path(__file__).parent
STATIC_DIR = FRONTEND_DIR / "static"
PAGES_DIR = FRONTEND_DIR / "pages"

# 需要处理的静态文件映射 {文件路径: [使用该文件的HTML页面]}
STATIC_FILES = {
    "static/css/aggregations.css": ["pages/aggregations.html"],
    "static/css/templates-new.css": ["pages/templates.html"],
    "static/css/tasks-new.css": ["pages/tasks.html"],
    "static/css/dashboard.css": ["pages/dashboard.html"],
    "static/css/settings.css": ["pages/settings.html"],
    "static/js/api/templates.js": ["pages/templates.html"],
    "static/js/api/tasks.js": ["pages/tasks.html"],
    "static/js/api/common.js": ["pages/tasks.html", "pages/templates.html"],
    "static/js/utils.js": ["pages/tasks.html"],
    "static/js/navigation.js": ["pages/dashboard.html"],
    "static/css/mailbox.css": ["pages/mailbox.html"],
    "static/js/api/mailbox.js": ["pages/mailbox.html"],
    "static/css/agent.css": ["pages/agent.html"],
    "static/js/api/agent.js": ["pages/agent.html"],
    "static/js/agent.js": ["pages/agent.html"],
}


def get_file_hash(filepath: Path, length=8) -> str:
    """计算文件的MD5哈希值（取前N位）"""
    if not filepath.exists():
        print(f"⚠️  文件不存在: {filepath}")
        return "00000000"[:length]
    
    md5 = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            md5.update(chunk)
    return md5.hexdigest()[:length]


def update_html_file(html_path: Path, static_path: str, version_hash: str):
    """更新HTML文件中的静态文件引用，添加或更新版本号"""
    if not html_path.exists():
        print(f"⚠️  HTML文件不存在: {html_path}")
        return False
    
    content = html_path.read_text(encoding='utf-8')
    
    # 构建正则表达式，匹配带或不带版本号的引用
    # 例如: /frontend/static/css/file.css 或 /frontend/static/css/file.css?v=xxx
    escaped_path = re.escape(f"/frontend/{static_path}")
    pattern = f'({escaped_path})(\\?v=[a-zA-Z0-9]+)?'
    replacement = f'\\1?v={version_hash}'
    
    new_content, count = re.subn(pattern, replacement, content)
    
    if count > 0 and new_content != content:
        html_path.write_text(new_content, encoding='utf-8')
        return True
    
    return False


def main():
    """主函数：遍历所有静态文件，计算哈希并更新HTML引用"""
    seperator = "=" * 60
    print(seperator)
    print("🔄 开始更新前端静态文件版本号...\n")
    
    updated_count = 0
    total_count = 0
    
    for idx, (static_path, html_files) in enumerate(STATIC_FILES.items()):
        static_file = FRONTEND_DIR / static_path
        version_hash = get_file_hash(static_file)
        
        print(f"📄 [{idx}] {static_path}")
        print(f"   Hash: {version_hash}")
        
        for html_file in html_files:
            html_path = FRONTEND_DIR / html_file
            total_count += 1
            
            if update_html_file(html_path, static_path, version_hash):
                print(f"   ✅ 已更新: {html_file}")
                updated_count += 1
            else:
                print(f"   ⏭️  无需更新: {html_file}")
        
        print()
    
    print(f"✨ 完成！共检查 {total_count} 个引用，更新了 {updated_count} 个")
    print(seperator + "\n")


if __name__ == "__main__":
    main()
