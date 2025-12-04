from typing import List, Dict, Any, Union, Literal
from pydantic import BaseModel

class AgentResponseItem(BaseModel):
    """Agent响应的单个内容块"""
    format: Literal["text", "table"]
    content: Union[str, Dict[str, Any]]
    # 对于 table 格式，content 应该是 {"columns": [...], "rows": [...]}
    # 对于 text 格式，content 是字符串

class AgentResponse(BaseModel):
    """Agent的完整响应"""
    items: List[AgentResponseItem]
