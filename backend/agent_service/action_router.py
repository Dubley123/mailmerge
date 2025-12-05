"""
Action Router - ACTION识别器
负责识别用户自然语言的意图，返回对应的ACTION类型
"""
from enum import Enum

from .llm_client import LLMClient
from backend.logger import get_logger

logger = get_logger(__name__)


class ActionType(Enum):
    """支持的ACTION类型"""
    SQL_QUERY = "SQL_QUERY"           # SQL查询
    CREATE_TEMPLATE = "CREATE_TEMPLATE"  # 创建模板
    SEND_EMAIL = "SEND_EMAIL"          # 发送邮件
    UNKNOWN = "UNKNOWN"                # 未知/无法识别


class ActionRouter:
    """ACTION识别路由器
    
    使用LLM识别用户意图，返回对应的ACTION类型
    """
    
    def __init__(self):
        # LLMClient 内部会自动加载环境变量配置
        self.llm_client = LLMClient()
    
    def route(self, user_input: str) -> ActionType:
        """识别用户输入的意图，返回ACTION类型
        
        Args:
            user_input: 用户的自然语言输入
            
        Returns:
            ActionType枚举值
        """
        # 系统提示词：专门用于识别ACTION
        system_prompt = """你是一个意图识别助手，负责识别用户输入属于哪种操作类型。

支持的操作类型：
1. `SQL_QUERY`: 用户想要查询数据库信息（查询、统计、列出、显示等）
2. `CREATE_TEMPLATE`: 用户想要创建数据收集模板（创建模板、生成表单、设计模板等）
3. `SEND_EMAIL`: 用户想要发送邮件（发送邮件、发信、通知某人等）
4. `UNKNOWN`: 无法识别的请求

请根据用户输入返回对应的操作类型。只返回类型名称，不要有其他内容。"""

        try:
            response = self.llm_client.chat(
                system_prompt=system_prompt,
                user_message=user_input,
                temperature=0.1
            )
            
            # LLMClient.chat 返回的是字典，content 字段包含回复内容
            result = response.get("content", "").strip().upper()
            
            logger.info(f"ACTION识别的自然语言结果: {result}")
            
            # 解析返回结果
            if "SQL_QUERY" in result or "SQL" in result:
                return ActionType.SQL_QUERY
            elif "CREATE_TEMPLATE" in result or "TEMPLATE" in result:
                return ActionType.CREATE_TEMPLATE
            elif "SEND_EMAIL" in result or "EMAIL" in result or "SEND MAIL" in result:
                return ActionType.SEND_EMAIL
            else:
                return ActionType.UNKNOWN
                
        except Exception as e:
            logger.error(f"ACTION识别失败: {e}")
            return ActionType.UNKNOWN
