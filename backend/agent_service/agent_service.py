"""
Agent Service - 统一入口
提供外部调用的标准接口，负责调度各个ACTION子目录
"""
from typing import Dict, Any, Optional

from .config import Config
from .action_router import ActionRouter, ActionType
from .llm_client import LLMClient

# 导入各个ACTION子目录的入口函数
from .sql_query.handler import handle_sql_query
from .create_template.handler import handle_create_template


def process_user_query(
    user_input: str,
    config: Optional[Config] = None,
    user_id: Optional[int] = None
) -> str:
    """统一入口函数 - 处理用户的自然语言请求
    
    工作流程：
    1. 识别用户意图（ACTION类型）
    2. 调用对应ACTION子目录的处理函数
    3. 用自然语言包装返回结果
    
    Args:
        user_input: 用户的自然语言输入
        config: 配置对象（可选，默认从环境变量加载）
        user_id: 用户ID（CREATE_TEMPLATE等需要用户身份的操作必须提供）
        
    Returns:
        str: 自然语言形式的执行结果
    """
    # 加载配置
    cfg = config or Config.from_env()
    
    # 第一步：识别ACTION
    router = ActionRouter(cfg)
    action = router.route(user_input)
    
    print(f"[INFO] 识别到ACTION: {action.value}")
    
    # 第二步：调用对应的ACTION处理器
    try:
        if action == ActionType.SQL_QUERY:
            result = handle_sql_query(user_input, cfg, user_id=user_id)
            return _format_sql_query_result(result)
        
        elif action == ActionType.CREATE_TEMPLATE:
            result = handle_create_template(user_input, cfg, user_id=user_id)
            return _format_create_template_result(result)
        
        else:  # ActionType.UNKNOWN
            return "抱歉，我无法理解您的请求。请尝试更明确地描述您的需求，例如：\n- '查询所有院系的名称'\n- '创建一个收集学生信息的模板'"
    
    except Exception as e:
        print(f"[ERROR] 处理请求时发生错误: {e}")
        return f"处理请求时发生错误：{str(e)}"


def _format_sql_query_result(result: Dict[str, Any]) -> str:
    """格式化SQL查询结果为自然语言
    
    Args:
        result: SQL查询返回的结果字典
        
    Returns:
        str: 自然语言描述
    """
    if result["status"] == "success":
        data = result["data"]
        rows = data.get("rows", [])
        row_count = len(rows)
        permission_warning = data.get("permission_warning")
        
        # 构建自然语言响应
        response = ""
        
        # 如果有权限警告，优先显示
        if permission_warning:
            response += f"⚠️ **权限提示**：{permission_warning}\n\n"
            
        response += f"查询成功！共找到 {row_count} 条记录。\n\n"
        
        if row_count > 0:
            # 显示列名
            columns = data.get("columns", [])
            response += f"列名: {', '.join(columns)}\n\n"
            
            # 显示前5条数据
            display_count = min(5, row_count)
            response += "查询结果：\n"
            for i, row in enumerate(rows[:display_count], 1):
                response += f"{i}. {row}\n"
            
            if row_count > 5:
                response += f"\n...还有 {row_count - 5} 条记录未显示"
        else:
            response += "未找到符合条件的数据。"
        
        return response
    
    else:
        # 查询失败
        error_msg = result["data"].get("message", "未知错误")
        return f"查询失败：{error_msg}"


def _format_create_template_result(result: Dict[str, Any]) -> str:
    """格式化创建模板结果为自然语言
    
    Args:
        result: 创建模板返回的结果字典
        
    Returns:
        str: 自然语言描述
    """
    if result["status"] == "success":
        data = result["data"]
        template_name = data.get("template_name", "未命名模板")
        return f"模板创建成功！\n模板名称：{template_name}\n您可以在模板管理页面查看和使用该模板。"
    
    else:
        error_msg = result["data"].get("message", "未知错误")
        return f"模板创建失败：{error_msg}"
