from typing import Dict, Any
from datetime import datetime, timedelta
from ..config import Config
from ..llm_client import LLMClient
from .prompt_generator import generate_create_task_prompt
from .utils import fetch_available_templates, fetch_available_teachers
from backend.logger import get_logger
from backend.database.db_config import get_session_factory
from backend.database.models import CollectTask, CollectTaskTarget, TaskStatus, Secretary
from backend.utils import get_utc_now, ensure_utc

logger = get_logger(__name__)

def handle_create_task(user_input: str, user_id: int = None) -> Dict[str, Any]:
    """处理创建任务的请求"""
    if user_id is None:
        return {"status": "error", "data": {"message": "缺少 user_id，无法创建任务"}}

    # 1. 获取上下文信息
    templates = fetch_available_templates(user_id)
    teachers = fetch_available_teachers(user_id)
    
    if not templates:
        return {
            "status": "error", 
            "data": {"message": "当前没有可用的表单模板。请先使用'创建模板'功能创建一个模板，然后再创建任务。"}
        }

    # 2. 生成Prompt
    prompt_data = generate_create_task_prompt(user_id, templates, teachers)
    system_prompt = prompt_data["system_prompt"]
    tools = prompt_data["tools"]

    logger.info(f"Create Task System Prompt:\n{system_prompt}")

    # 3. 调用LLM
    llm_client = LLMClient()
    conversation_history = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input}
    ]

    try:
        llm_response = llm_client.chat_with_history(
            messages=conversation_history,
            tools=tools,
            temperature=0.1
        )

        logger.info(f"Create Task LLM Response:\n{llm_response}")

        if llm_response["type"] != "tool_call":
            # LLM 拒绝生成或有其他回复
            return {
                "status": "error", 
                "data": {"message": llm_response.get("content", "无法理解您的请求，请提供更详细的任务信息。")}
            }

        tool_call = llm_response["tool_calls"][0]
        if tool_call["name"] != "create_task":
            return {"status": "error", "data": {"message": "LLM调用了错误的工具"}}

        args = tool_call.get("arguments", {})
        
        # 4. 验证参数
        template_id = args.get("template_id")
        teacher_ids = args.get("teacher_ids", [])
        
        # 验证模板是否存在
        if not any(t['id'] == template_id for t in templates):
            return {"status": "error", "data": {"message": f"指定的模板ID {template_id} 不存在或不可用"}}
            
        # 验证教师是否存在
        valid_teacher_ids = {t['id'] for t in teachers}
        invalid_ids = [tid for tid in teacher_ids if tid not in valid_teacher_ids]
        if invalid_ids:
            return {"status": "error", "data": {"message": f"以下教师ID无效或不在您的管辖范围内: {invalid_ids}"}}
            
        if not teacher_ids:
             return {"status": "error", "data": {"message": "未指定任何有效的目标教师"}}

        # 5. 执行创建任务逻辑
        return _create_task_in_db(user_id, args)

    except Exception as e:
        logger.error(f"处理create_task过程中发生异常: {e}", exc_info=True)
        return {"status": "error", "data": {"message": f"处理请求时发生错误: {str(e)}"}}

def _create_task_in_db(user_id: int, args: Dict[str, Any]) -> Dict[str, Any]:
    """在数据库中创建任务"""
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        # 检查名称重复
        existing = db.query(CollectTask).filter(CollectTask.name == args["name"]).first()
        if existing:
             return {"status": "error", "data": {"message": f"任务名称 '{args['name']}' 已存在，请更换名称"}}

        now = get_utc_now()
        warning_msgs = []
        
        # 1. 处理开始时间
        started_time = None
        if args.get("started_time"):
            try:
                started_time = datetime.fromisoformat(args["started_time"])
                started_time = ensure_utc(started_time)
            except ValueError:
                return {"status": "error", "data": {"message": "开始时间格式无效，请使用ISO8601格式"}}
        
        # 默认开始时间：当前时间 + 5分钟
        default_start_time = now + timedelta(minutes=5)
        
        # 校验开始时间：如果未指定，或指定的时间早于当前时间（即立即发布），则强制设为默认时间
        if not started_time or started_time <= now:
            if started_time and started_time <= now:
                warning_msgs.append("考虑到安全性问题，不支持通过Agent直接发布任务，已自动调整为5分钟后开始。")
            started_time = default_start_time
            
        # 2. 处理截止时间
        deadline = None
        if args.get("deadline"):
            try:
                deadline = datetime.fromisoformat(args["deadline"])
                deadline = ensure_utc(deadline)
            except ValueError:
                return {"status": "error", "data": {"message": "截止时间格式无效，请使用ISO8601格式"}}
        
        # 默认截止时间：开始时间 + 7天
        default_deadline = started_time + timedelta(days=7)
        
        # 校验截止时间：如果未指定，或截止时间早于开始时间
        if not deadline or deadline <= started_time:
            if deadline and deadline <= started_time:
                warning_msgs.append("任务截止时间必须晚于开始时间，已自动调整为开始时间7天后。")
            deadline = default_deadline

        # 3. 确定状态 - 始终为 DRAFT
        task_status = TaskStatus.DRAFT

        new_task = CollectTask(
            name=args["name"],
            description=args.get("description"),
            started_time=started_time,
            deadline=deadline,
            template_id=args["template_id"],
            status=task_status,
            created_by=user_id,
            mail_content_template={
                'subject': args["mail_subject"],
                'content': args["mail_content"]
            },
            extra=None
        )
        
        db.add(new_task)
        db.flush() # 获取ID
        
        # 添加目标教师
        for tid in args["teacher_ids"]:
            target = CollectTaskTarget(task_id=new_task.id, teacher_id=tid)
            db.add(target)
            
        db.commit()
        
        response_data = {
            "task_id": new_task.id,
            "task_name": new_task.name,
            "teacher_count": len(args["teacher_ids"]),
            "status": task_status.value,
            "started_time": started_time.isoformat(),
            "deadline": deadline.isoformat()
        }
        
        if warning_msgs:
            response_data["warning"] = "\n".join(warning_msgs)
            
        return {
            "status": "success",
            "data": response_data
        }
        
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()
