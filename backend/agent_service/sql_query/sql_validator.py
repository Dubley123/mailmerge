"""
SQL Validator - SQL安全校验器
使用sqlglot进行专业的SQL解析和安全检查
"""
from typing import Tuple, List

try:
    import sqlglot
    from sqlglot import parse_one, exp
    SQLGLOT_AVAILABLE = True
except ImportError:
    SQLGLOT_AVAILABLE = False
    import re


class SQLValidator:
    """SQL安全校验器
    
    校验规则：
    - 仅允许SELECT查询语句
    - 禁止多语句SQL（防止SQL注入）
    - 表名必须在白名单内
    - 禁止危险函数
    """
    
    def __init__(self, dialect: str = "postgres"):
        self.dialect = dialect
    
    def validate(self, sql: str, allowed_tables: List[str]) -> Tuple[bool, str]:
        """校验SQL的安全性
        
        Args:
            sql: 要校验的SQL语句
            allowed_tables: 允许查询的表名列表
            
        Returns:
            (is_valid, message): (是否有效, 错误信息或"OK")
        """
        if not sql or not sql.strip():
            return False, "SQL语句为空"
        
        sql = sql.strip()
        
        # 使用sqlglot进行专业校验
        if SQLGLOT_AVAILABLE:
            return self._validate_with_sqlglot(sql, allowed_tables)
        else:
            # 降级方案：简单的正则校验
            return self._validate_with_regex(sql, allowed_tables)
    
    def _validate_with_sqlglot(self, sql: str, allowed_tables: List[str]) -> Tuple[bool, str]:
        """使用sqlglot进行专业校验"""
        try:
            # 解析SQL
            parsed = parse_one(sql, dialect=self.dialect)
            
            # 1. 检查是否只有一条语句
            if ";" in sql.rstrip(";"):
                return False, "不允许多条SQL语句"
            
            # 2. 检查是否为SELECT语句
            if not isinstance(parsed, exp.Select):
                return False, f"仅允许SELECT查询，当前类型: {type(parsed).__name__}"
            
            # 3. 检查表名是否在白名单内
            tables = [table.name for table in parsed.find_all(exp.Table)]
            for table in tables:
                if table not in allowed_tables:
                    return False, f"表 '{table}' 不在允许查询的范围内。允许的表: {', '.join(allowed_tables)}"
            
            # 4. 检查是否包含危险函数（简单的字符串检查）
            sql_upper = sql.upper()
            dangerous_functions = ["PG_SLEEP", "PG_READ_FILE", "PG_WRITE_FILE", "PG_LS_DIR"]
            for func in dangerous_functions:
                if func in sql_upper:
                    return False, f"禁止使用危险函数: {func.lower()}"
            
            return True, "OK"
            
        except Exception as e:
            return False, f"SQL解析失败: {str(e)}"
    
    def _validate_with_regex(self, sql: str, allowed_tables: List[str]) -> Tuple[bool, str]:
        """降级方案：使用正则表达式进行简单校验"""
        sql_upper = sql.upper()
        
        # 1. 检查多语句
        if sql.count(";") > 1:
            return False, "不允许多条SQL语句"
        
        # 2. 检查是否为SELECT
        if not sql_upper.strip().startswith("SELECT"):
            return False, "仅允许SELECT查询"
        
        # 3. 检查危险关键字
        dangerous_keywords = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE", "TRUNCATE"]
        for keyword in dangerous_keywords:
            if keyword in sql_upper:
                return False, f"禁止使用关键字: {keyword}"
        
        # 4. 检查危险函数
        dangerous_functions = ["PG_SLEEP", "PG_READ_FILE", "PG_WRITE_FILE"]
        for func in dangerous_functions:
            if func in sql_upper:
                return False, f"禁止使用危险函数: {func}"
        
        return True, "OK"
