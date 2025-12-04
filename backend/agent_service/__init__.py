"""
Agent Service - 统一导出接口
"""
from .agent_service import process_user_query
from .config import Config
from .action_router import ActionType

__all__ = [
    "process_user_query",  # 主入口函数
    "Config",              # 配置类
    "ActionType"           # ACTION类型枚举
]

__version__ = "2.0.0"
