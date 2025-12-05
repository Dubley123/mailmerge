"""
SQL Query Handler - SQL查询ACTION的入口函数
负责协调整个SQL查询流程
"""
from typing import Dict, Any
from pathlib import Path

from ..config import Config
from ..llm_client import LLMClient
from .prompt_generator import generate_sql_query_prompt
from .sql_validator import SQLValidator
from .sql_executor import SQLExecutor
from backend.logger import get_logger

logger = get_logger(__name__)


def handle_sql_query(user_input: str, user_id: int = None) -> Dict[str, Any]:
    """SQL查询ACTION的处理入口
    
    工作流程：
    1. 生成SQL查询的Prompt
    2. 调用LLM生成SQL
    3. 校验SQL安全性
    4. 执行SQL查询（使用项目统一的数据库连接）
    5. 如果失败，反馈错误并重试
    
    Args:
        user_input: 用户的自然语言查询请求
        user_id: 当前用户的ID，用于权限控制
        
    Returns:
        {
            "status": "success" | "error",
            "data": {
                "sql": "...",
                "rows": [...],
                "columns": [...],
                "row_count": int,
                "permission_warning": str | None  # 新增字段
            } | {"message": "...", "last_error": "..."}
        }
    """
    # 初始化组件（数据库使用项目统一配置）
    config = Config.from_env()
    llm_client = LLMClient()
    validator = SQLValidator(dialect="postgres")
    executor = SQLExecutor()  # 不再需要传递config
    
    # 生成Prompt和工具定义
    prompt_data = generate_sql_query_prompt(user_id=user_id)
    system_prompt = prompt_data["system_prompt"]
    tools = prompt_data["tools"]
    allowed_tables = prompt_data["allowed_tables"]
    
    # 重试逻辑
    max_retries = config.MAX_RETRY
    conversation_history = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input}
    ]
    
    for attempt in range(1, max_retries + 1):
        logger.info(f"SQL查询尝试 {attempt}/{max_retries}")
        
        try:
            # 调用LLM生成SQL
            logger.info("正在调用 LLM 生成 SQL...")
            llm_response = llm_client.chat_with_history(
                messages=conversation_history,
                tools=tools,
                temperature=0.1
            )
            
            # 检查是否是Tool Calling响应
            if llm_response["type"] != "tool_call":
                error_msg = "LLM未返回SQL工具调用"
                logger.error(error_msg)
                conversation_history.append({
                    "role": "assistant",
                    "content": llm_response["content"]
                })
                conversation_history.append({
                    "role": "user",
                    "content": "请使用run_sql工具返回SQL查询语句"
                })
                continue
            
            # 提取SQL
            tool_call = llm_response["tool_calls"][0]
            if tool_call["name"] != "run_sql":
                error_msg = f"LLM调用了错误的工具: {tool_call['name']}"
                logger.error(error_msg)
                continue
            
            arguments = tool_call["arguments"]
            sql = arguments.get("sql", "").strip()
            permission_warning = arguments.get("permission_warning")
            
            logger.info(f"LLM生成SQL: {sql}")
            if permission_warning:
                logger.warning(f"权限警告: {permission_warning}")
            
            # 校验SQL安全性
            is_valid, validation_msg = validator.validate(sql, allowed_tables)
            if not is_valid:
                logger.warning(f"SQL校验失败: {validation_msg}")
                # 反馈给LLM重新生成
                conversation_history.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{"id": tool_call["id"], "type": "function", "function": {"name": "run_sql", "arguments": arguments}}]
                })
                conversation_history.append({
                    "role": "user",
                    "content": f"SQL校验失败：{validation_msg}\n请修正后重新生成SQL。"
                })
                continue
            
            # 执行SQL
            logger.info("正在执行 SQL 查询...")
            result = executor.execute(sql)
            
            if result["status"] == "success":
                logger.info(f"SQL执行成功，返回 {result['data']['row_count']} 行")
                # 将权限警告添加到返回结果中
                result["data"]["permission_warning"] = permission_warning
                return result
            else:
                # SQL执行失败，反馈给LLM
                error_msg = result["data"]["message"]
                logger.warning(f"SQL执行失败: {error_msg}")
                conversation_history.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{"id": tool_call["id"], "type": "function", "function": {"name": "run_sql", "arguments": arguments}}]
                })
                conversation_history.append({
                    "role": "user",
                    "content": f"SQL执行失败：{error_msg}\n请根据错误信息修正SQL并重新生成。"
                })
        
        except Exception as e:
            logger.error(f"处理过程中发生异常: {e}", exc_info=True)
            conversation_history.append({
                "role": "user",
                "content": f"发生错误：{str(e)}\n请重新生成SQL。"
            })
    
    # 所有重试都失败
    logger.error(f"经过 {max_retries} 次尝试仍未成功生成有效的SQL查询")
    return {
        "status": "error",
        "data": {
            "message": f"经过 {max_retries} 次尝试仍未成功生成有效的SQL查询",
            "last_error": "达到最大重试次数"
        }
    }
