"""
Create Template Handler - 创建模板ACTION的入口函数
负责协调整个模板创建流程
"""
from typing import Dict, Any

from backend.database.db_config import get_session_factory
from backend.utils.template_utils import create_template_core
from ..config import Config
from ..llm_client import LLMClient
from .prompt_generator import generate_create_template_prompt
from backend.logger import get_logger

logger = get_logger(__name__)


def handle_create_template(user_input: str, config: Config, user_id: int = None) -> Dict[str, Any]:
    """创建模板ACTION的处理入口
    
    工作流程：
    1. 生成创建模板的Prompt
    2. 调用LLM理解需求并生成模板结构
    3. 验证生成的模板格式
    4. 调用核心业务逻辑创建模板
    
    Args:
        user_input: 用户的自然语言创建模板请求
        config: 配置对象
        user_id: 用户ID（必须提供）
        
    Returns:
        {
            "status": "success" | "error",
            "data": {
                "template_id": int,
                "template_name": str,
                ...
            } | {"message": str}
        }
    """
    # 检查 user_id
    if user_id is None:
        return {
            "status": "error",
            "data": {
                "message": "缺少 user_id 参数，无法创建模板"
            }
        }
    
    # 初始化组件
    llm_client = LLMClient(config)
    SessionLocal = get_session_factory()
    
    # 生成Prompt和工具定义
    prompt_data = generate_create_template_prompt()
    system_prompt = prompt_data["system_prompt"]
    tools = prompt_data["tools"]
    
    # 重试逻辑
    max_retries = config.MAX_RETRY
    conversation_history = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input}
    ]
    
    for attempt in range(1, max_retries + 1):
        logger.info(f"创建模板尝试 {attempt}/{max_retries}")
        
        try:
            # 调用LLM生成模板定义
            logger.info("正在调用 LLM 生成模板定义...")
            llm_response = llm_client.chat_with_history(
                messages=conversation_history,
                tools=tools,
                temperature=0.1
            )
            
            # 检查是否是Tool Calling响应
            if llm_response["type"] != "tool_call":
                error_msg = "LLM未返回create_template工具调用"
                logger.error(error_msg)
                conversation_history.append({
                    "role": "assistant",
                    "content": llm_response["content"]
                })
                conversation_history.append({
                    "role": "user",
                    "content": "请使用create_template工具返回模板定义"
                })
                continue
            
            # 提取模板定义
            tool_call = llm_response["tool_calls"][0]
            if tool_call["name"] != "create_template":
                error_msg = f"LLM调用了错误的工具: {tool_call['name']}"
                logger.error(error_msg)
                continue
            
            template_data = tool_call["arguments"]
            logger.info(f"LLM生成模板定义: {template_data}")
            
            # 调用核心业务逻辑创建模板
            db = SessionLocal()
            try:
                logger.info("正在调用核心业务逻辑创建模板...")
                result = create_template_core(
                    name=template_data.get("name"),
                    fields=template_data.get("fields", []),
                    description=template_data.get("description"),
                    created_by=user_id,
                    db=db
                )
                
                if result["success"]:
                    logger.info(f"模板创建成功: {result}")
                    return {
                        "status": "success",
                        "data": {
                            "template_id": result["data"]["template_id"],
                            "template_name": template_data["name"],
                            "field_count": len(template_data.get("fields", []))
                        }
                    }
                else:
                    # 核心业务逻辑返回失败，反馈给LLM
                    error_msg = result["message"]
                    logger.warning(f"模板创建失败: {error_msg}")
                    conversation_history.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{"id": tool_call["id"], "type": "function", "function": {"name": "create_template", "arguments": template_data}}]
                    })
                    conversation_history.append({
                        "role": "user",
                        "content": f"创建失败：{error_msg}\n请根据错误信息调整模板定义。"
                    })
            finally:
                db.close()
        
        except Exception as e:
            logger.error(f"处理过程中发生异常: {e}", exc_info=True)
            conversation_history.append({
                "role": "user",
                "content": f"发生错误：{str(e)}\n请重新生成模板定义。"
            })
    
    # 所有重试都失败
    logger.error(f"经过 {max_retries} 次尝试仍未成功创建模板")
    return {
        "status": "error",
        "data": {
            "message": f"经过 {max_retries} 次尝试仍未成功创建模板",
            "last_error": "达到最大重试次数"
        }
    }
