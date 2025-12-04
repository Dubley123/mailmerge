"""
Action Router - ACTION识别器
负责识别用户自然语言的意图，返回对应的ACTION类型
"""
from typing import Dict, Any
from enum import Enum

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from .config import Config


class ActionType(Enum):
    """支持的ACTION类型"""
    SQL_QUERY = "SQL_QUERY"           # SQL查询
    CREATE_TEMPLATE = "CREATE_TEMPLATE"  # 创建模板
    UNKNOWN = "UNKNOWN"                # 未知/无法识别


class ActionRouter:
    """ACTION识别路由器
    
    使用LLM识别用户意图，返回对应的ACTION类型
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.client = None
        
        if OPENAI_AVAILABLE and self.config.API_KEY:
            self.client = OpenAI(
                api_key=self.config.API_KEY,
                base_url=self.config.BASE_URL,
                timeout=self.config.TIMEOUT
            )
    
    def route(self, user_input: str) -> ActionType:
        """识别用户输入的意图，返回ACTION类型
        
        Args:
            user_input: 用户的自然语言输入
            
        Returns:
            ActionType枚举值
        """
        if not self.client:
            print("[警告] LLM客户端未初始化，默认返回UNKNOWN")
            return ActionType.UNKNOWN
        
        # 系统提示词：专门用于识别ACTION
        system_prompt = """你是一个意图识别助手，负责识别用户输入属于哪种操作类型。

支持的操作类型：
1. `SQL_QUERY`: 用户想要查询数据库信息（查询、统计、列出、显示等）
2. `CREATE_TEMPLATE`: 用户想要创建数据收集模板（创建模板、生成表单、设计模板等）
3. `UNKNOWN`: 无法识别的请求

请根据用户输入返回对应的操作类型。只返回类型名称，不要有其他内容。"""

        try:
            response = self.client.chat.completions.create(
                model=self.config.MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input}
                ],
                temperature=0.1
            )
            
            result = response.choices[0].message.content.strip().upper()
            
            print(f"[INFO] ACTION识别的自然语言结果: {result}")
            
            # 解析返回结果
            if "SQL_QUERY" in result or "SQL" in result:
                return ActionType.SQL_QUERY
            elif "CREATE_TEMPLATE" in result or "TEMPLATE" in result:
                return ActionType.CREATE_TEMPLATE
            else:
                return ActionType.UNKNOWN
                
        except Exception as e:
            print(f"[错误] ACTION识别失败: {e}")
            return ActionType.UNKNOWN
