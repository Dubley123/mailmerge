from typing import List, Dict, Any, Optional
from ..llm_client import LLMClient
from backend.logger import get_logger

logger = get_logger(__name__)

def infer_task_id(user_input: str, tasks: List[Dict[str, Any]]) -> Optional[int]:
    """
    Ask LLM to infer if the user's email intent is related to a specific existing task.
    
    Args:
        user_input: The user's natural language request.
        tasks: List of available tasks (id, name, description).
        
    Returns:
        Task ID (int) if a strong correlation is found, otherwise None.
    """
    if not tasks:
        return None

    # Format task list for prompt
    tasks_str = "\n".join([
        f"- ID: {t['id']}, Name: {t['name']}, Description: {t['description'] or 'None'}"
        for t in tasks
    ])

    system_prompt = f"""你是一个智能助手，负责分析用户的邮件发送请求是否与某个现有的“数据收集任务”相关联。

以下是用户创建的所有现有任务列表：
{tasks_str}

用户的请求是：
"{user_input}"

请分析用户的请求内容，判断这封邮件是否是为了某个特定任务而发送的（例如：催促提交、任务提醒、关于该任务的补充说明等）。
- 如果你能确定该邮件与列表中某个任务有明确的关联，请返回该任务的ID。
- 如果无法确定关联，或者请求与任何任务都无关，请返回 -1。

请只输出一个数字（任务ID或-1），不要包含任何其他文字或解释。
"""

    llm_client = LLMClient()
    
    try:
        # We use a simple chat call here, no tools needed, just expecting a number.
        response = llm_client.chat(
            system_prompt=system_prompt,
            user_message="请分析并返回ID", # The user input is already in system prompt context
            temperature=0.1
        )
        
        content = response.get("content", "").strip()
        logger.info(f"Task inference response: {content}")
        
        try:
            task_id = int(content)
        except ValueError:
            logger.warning(f"LLM returned non-integer for task inference: {content}")
            return None
            
        if task_id == -1:
            return None
            
        # Verify the ID is actually in our list
        valid_ids = {t['id'] for t in tasks}
        if task_id in valid_ids:
            return task_id
        else:
            logger.warning(f"LLM returned task ID {task_id} which is not in the valid list.")
            return None

    except Exception as e:
        logger.error(f"Error during task inference: {e}")
        return None
