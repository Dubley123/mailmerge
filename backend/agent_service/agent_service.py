"""
Agent Service - 统一入口
提供外部调用的标准接口，负责调度各个ACTION子目录
"""
from typing import Dict, Any, Optional, List

from .config import Config
from .action_router import ActionRouter, ActionType
from .llm_client import LLMClient
from .schemas import AgentResponse, AgentResponseItem
from backend.logger import get_logger

# 导入各个ACTION子目录的入口函数
from .sql_query.handler import handle_sql_query
from .create_template.handler import handle_create_template
from .send_email.handler import handle_send_email
from .create_task.handler import handle_create_task

logger = get_logger(__name__)


def process_user_query(
    user_input: str,
    user_id: Optional[int] = None
) -> AgentResponse:
    """统一入口函数 - 处理用户的自然语言请求
    
    工作流程：
    1. 识别用户意图（ACTION类型）
    2. 调用对应ACTION子目录的处理函数
    3. 用自然语言包装返回结果
    
    Args:
        user_input: 用户的自然语言输入
        user_id: 用户ID（CREATE_TEMPLATE等需要用户身份的操作必须提供）
        
    Returns:
        AgentResponse: 结构化的执行结果
    """
    # 加载配置
    logger.info("加载 Agent 配置...")
    cfg = Config.from_env()
    
    # 检查是否启用
    if not cfg.ENABLED:
        # 构造测试表格数据
        test_columns = ["姓名", "工号", "院系", "职称", "邮箱", "入职日期", "状态"]
        test_rows = [
            ["张三", "T2023001", "计算机学院", "教授", "zhangsan@example.com", "2020-01-01", "在职"],
            ["李四", "T2023002", "数学学院", "副教授", "lisi@example.com", "2021-03-15", "在职"],
            ["王五", "T2023003", "物理学院", "讲师", "wangwu@example.com", "2022-07-01", "在职"],
            ["赵六", "T2023004", "化学学院", "助教", "zhaoliu@example.com", "2023-09-01", "实习"],
            ["钱七", "T2023005", "外国语学院", "教授", "qianqi@example.com", "2019-11-11", "休假"]
        ]
        
        return AgentResponse(items=[
            AgentResponseItem(format="text", content="抱歉，智能助手功能当前未开启。请联系管理员启用该功能。\n\n以下是表格展示功能的测试样例："),
            AgentResponseItem(format="table", content={
                "columns": test_columns,
                "rows": test_rows
            })
        ])
    
    logger.info("=" * 50)
    logger.info(f"收到新的用户请求 [User ID: {user_id}]")
    logger.info(f"请求内容: {user_input}")
    
    # 第一步：识别ACTION
    logger.info("正在识别用户意图...")
    router = ActionRouter()
    action = router.route(user_input)
    
    logger.info(f"识别到ACTION: {action.value}")
    
    # 第二步：调用对应的ACTION处理器
    try:
        if action == ActionType.SQL_QUERY:
            logger.info("开始处理 SQL_QUERY 请求...")
            result = handle_sql_query(user_input, user_id=user_id)
            logger.info("SQL_QUERY 请求处理完成")
            return _format_sql_query_result(result)
        
        elif action == ActionType.CREATE_TEMPLATE:
            logger.info("开始处理 CREATE_TEMPLATE 请求...")
            result = handle_create_template(user_input, user_id=user_id)
            logger.info("CREATE_TEMPLATE 请求处理完成")
            return _format_create_template_result(result)

        elif action == ActionType.SEND_EMAIL:
            logger.info("开始处理 SEND_EMAIL 请求...")
            result = handle_send_email(user_input, user_id=user_id)
            logger.info("SEND_EMAIL 请求处理完成")
            return _format_send_email_result(result)

        elif action == ActionType.CREATE_TASK:
            logger.info("开始处理 CREATE_TASK 请求...")
            result = handle_create_task(user_input, user_id=user_id)
            logger.info("CREATE_TASK 请求处理完成")
            return _format_create_task_result(result)
        
        else:  # ActionType.UNKNOWN
            logger.warning("无法识别用户意图")
            return AgentResponse(items=[
                AgentResponseItem(format="text", content="抱歉，我无法理解您的请求。请尝试更明确地描述您的需求，例如：\n- '查询所有院系的名称'\n- '创建一个收集学生信息的模板'")
            ])
    
    except Exception as e:
        logger.error(f"处理请求时发生错误: {e}", exc_info=True)
        return AgentResponse(items=[
            AgentResponseItem(format="text", content=f"处理请求时发生错误：{str(e)}")
        ])


def _format_sql_query_result(result: Dict[str, Any]) -> AgentResponse:
    """格式化SQL查询结果为结构化响应
    
    Args:
        result: SQL查询返回的结果字典
        
    Returns:
        AgentResponse: 结构化响应
    """
    items = []
    
    if result["status"] == "success":
        data = result["data"]
        rows = data.get("rows", [])
        row_count = len(rows)
        permission_warning = data.get("permission_warning")
        
        # 1. 权限警告（如果有）
        if permission_warning:
            items.append(AgentResponseItem(
                format="text", 
                content=f"⚠️ **权限提示**：{permission_warning}"
            ))
            
        # 2. 结果摘要
        summary = f"查询成功！共找到 {row_count} 条记录。"
        if row_count == 0:
            summary += " 未找到符合条件的数据。"
        items.append(AgentResponseItem(format="text", content=summary))
        
        # 3. 数据表格（如果有数据）
        if row_count > 0:
            columns = data.get("columns", [])
            # 转换 rows 为字典列表（如果它们是元组或列表）
            # 假设 rows 是 list of tuples/lists，需要转为 list of dicts 以便前端更好处理，或者前端处理 list of lists
            # 这里为了通用性，我们保持 rows 为 list of lists/tuples，但在 content 中明确结构
            
            # 注意：SQLAlchemy 的 result.fetchall() 返回的是 Row 对象，可以像 tuple 一样索引
            # 为了 JSON 序列化，我们需要将其转换为 list
            serialized_rows = [list(row) for row in rows]
            
            items.append(AgentResponseItem(
                format="table",
                content={
                    "columns": columns,
                    "rows": serialized_rows
                }
            ))
            
            # 4. 截断提示（如果数据量很大，虽然这里已经是全量返回给前端了，前端可以做分页或截断显示）
            # 后端不再做截断，交给前端展示处理
            
    else:
        # 查询失败
        error_msg = result["data"].get("message", "未知错误")
        items.append(AgentResponseItem(format="text", content=f"查询失败：{error_msg}"))
        
    return AgentResponse(items=items)


def _format_create_template_result(result: Dict[str, Any]) -> AgentResponse:
    """格式化创建模板结果为结构化响应
    
    Args:
        result: 创建模板返回的结果字典
        
    Returns:
        AgentResponse: 结构化响应
    """
    items = []
    
    if result["status"] == "success":
        data = result["data"]
        template_name = data.get("template_name", "未命名模板")
        items.append(AgentResponseItem(
            format="text", 
            content=f"模板创建成功！\n模板名称：{template_name}\n您可以在模板管理页面查看和使用该模板。"
        ))
    
    else:
        error_msg = result["data"].get("message", "未知错误")
        items.append(AgentResponseItem(format="text", content=f"模板创建失败：{error_msg}"))
        
    return AgentResponse(items=items)


def _format_send_email_result(result: Dict[str, Any]) -> AgentResponse:
    """格式化发送邮件结果为结构化响应
    
    Args:
        result: 发送邮件返回的结果字典
        
    Returns:
        AgentResponse: 结构化响应
    """
    items = []
    
    if result["status"] == "success":
        data = result["data"]
        sent = data.get("sent", 0)
        total = data.get("total", 0)
        items.append(AgentResponseItem(
            format="text", 
            content=f"邮件发送完成！\n共尝试发送 {total} 封，成功 {sent} 封。"
        ))
    
    else:
        error_msg = result["data"].get("message", "未知错误")
        items.append(AgentResponseItem(format="text", content=f"邮件发送失败：{error_msg}"))
        
    return AgentResponse(items=items)


def _format_create_task_result(result: Dict[str, Any]) -> AgentResponse:
    """格式化创建任务结果为结构化响应
    
    Args:
        result: 创建任务返回的结果字典
        
    Returns:
        AgentResponse: 结构化响应
    """
    items = []
    
    if result["status"] == "success":
        data = result["data"]
        task_name = data.get("task_name", "未命名任务")
        teacher_count = data.get("teacher_count", 0)
        
        content = f"任务创建成功！\n任务名称：{task_name}\n已分配给 {teacher_count} 位教师。\n您可以在任务管理页面查看详情。"
        
        if data.get("warning"):
            content += f"\n\n⚠️ 注意：\n{data['warning']}"
            
        items.append(AgentResponseItem(
            format="text", 
            content=content
        ))
    
    else:
        error_msg = result["data"].get("message", "未知错误")
        items.append(AgentResponseItem(format="text", content=f"任务创建失败：{error_msg}"))
        
    return AgentResponse(items=items)
