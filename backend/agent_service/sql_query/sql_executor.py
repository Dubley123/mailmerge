"""
SQL Executor - SQL执行器
负责执行SQL查询，使用项目统一的数据库连接
"""
from typing import Dict, Any
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ...database.db_config import get_session_factory


class SQLExecutor:
    """SQL执行器
    
    负责执行SQL查询，使用项目统一的数据库配置
    """
    
    def __init__(self, config=None):
        """初始化SQL执行器
        
        Args:
            config: 配置对象（此处不再需要，保留参数为了兼容性）
        """
        self.SessionLocal = get_session_factory()
    
    def execute(self, sql: str) -> Dict[str, Any]:
        """执行SQL查询
        
        Args:
            sql: 要执行的SQL语句
            
        Returns:
            {
                "status": "success" | "error",
                "data": {
                    "sql": str,
                    "rows": List[tuple],
                    "columns": List[str],
                    "row_count": int
                } | {"message": str}
            }
        """
        db = self.SessionLocal()
        try:
            # 执行查询
            result = db.execute(text(sql))
            
            # 获取结果
            rows = result.fetchall()
            columns = list(result.keys())
            
            return {
                "status": "success",
                "data": {
                    "sql": sql,
                    "rows": [tuple(row) for row in rows],
                    "columns": columns,
                    "row_count": len(rows)
                }
            }
        
        except SQLAlchemyError as e:
            return {
                "status": "error",
                "data": {
                    "message": f"数据库错误: {str(e)}"
                }
            }
        
        except Exception as e:
            return {
                "status": "error",
                "data": {
                    "message": f"执行失败: {str(e)}"
                }
            }
        
        finally:
            db.close()
