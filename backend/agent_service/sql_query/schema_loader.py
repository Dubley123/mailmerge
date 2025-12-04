"""
Schema Loader
负责加载和缓存数据库Schema文件内容
"""
from pathlib import Path
import re
from typing import List, Optional

class SchemaLoader:
    _instance = None
    _schema_text: Optional[str] = None
    _table_names: Optional[List[str]] = None
    
    # 数据库Schema文件路径 (相对于当前文件)
    # 由于 schema_loader.py 和 database.md 都在 sql_query 目录下
    SCHEMA_FILE_PATH = Path(__file__).parent / "database.md"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SchemaLoader, cls).__new__(cls)
        return cls._instance

    def load_schema(self) -> str:
        """加载数据库Schema内容（带缓存）"""
        if self._schema_text is None:
            self._schema_text = self._read_schema_file()
        return self._schema_text

    def get_table_names(self) -> List[str]:
        """获取所有表名列表（带缓存）"""
        if self._table_names is None:
            schema_text = self.load_schema()
            self._table_names = self._extract_table_names(schema_text)
        return self._table_names

    def _read_schema_file(self) -> str:
        """读取Schema文件内容"""
        if not self.SCHEMA_FILE_PATH.exists():            
            return "## 数据库Schema未找到\n请确保database.md文件存在"
        
        try:
            return self.SCHEMA_FILE_PATH.read_text(encoding="utf-8")
        except Exception as e:
            return f"## 读取数据库Schema失败\n错误: {str(e)}"

    def _extract_table_names(self, schema_text: str) -> List[str]:
        """从Schema文本中提取表名列表"""
        tables = set()
        
        # 匹配格式: # 1. department（院系）
        # 这里的正则需要匹配: # 数字. 表名(中文说明)
        pattern = r'#\s*\d+\.\s*(\w+)'
        tables.update(re.findall(pattern, schema_text))
        
        # 也可以保留之前的匹配逻辑作为备选，以防格式变化
        # 匹配 ### 表名: xxx
        pattern1 = r'###\s*表名[:：]\s*`?(\w+)`?'
        tables.update(re.findall(pattern1, schema_text))
        
        # 匹配 ## xxx 表
        pattern2 = r'##\s+(\w+)\s*表'
        tables.update(re.findall(pattern2, schema_text))
        
        # 匹配 CREATE TABLE xxx
        pattern3 = r'CREATE TABLE\s+`?(\w+)`?'
        tables.update(re.findall(pattern3, schema_text, re.IGNORECASE))
        
        return sorted(list(tables))

# 全局单例实例
schema_loader = SchemaLoader()
