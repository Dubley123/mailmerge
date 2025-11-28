"""
任务相关 API 路由
处理收集任务的创建、查看、更新等操作
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone
from backend.utils import get_utc_now, ensure_utc

from backend.database.db_config import get_db_session
from backend.database.models import (
    CollectTask, CollectTaskTarget, Secretary, Teacher,
    TemplateForm, ReceivedEmail, TaskStatus, TemplateFormField,
    ReceivedAttachment, Aggregation
)
from backend.api.auth import get_current_user
from backend.services.task_service import perform_aggregation, check_task_status

router = APIRouter()


# ==================== Pydantic 模型 ====================

class TaskListItem(BaseModel):
    """任务列表项"""
    id: int
    name: str
    started_time: Optional[datetime]
    deadline: Optional[datetime]
    template_name: str
    replied_count: int
    total_count: int
    status: str
    created_at: datetime


class TeacherDetail(BaseModel):
    """教师详情"""
    id: int
    name: str
    email: str
    has_replied: bool


class TaskDetailResponse(BaseModel):
    """任务详情响应"""
    id: int
    name: str
    description: Optional[str]
    started_time: Optional[datetime]
    deadline: Optional[datetime]
    template_id: int
    template_name: str
    mail_subject: Optional[str]
    mail_content: Optional[str]
    status: str
    teachers: List[TeacherDetail]


class CreateTaskRequest(BaseModel):
    """创建任务请求"""
    name: str = Field(..., min_length=1, max_length=255, description="任务名称")
    description: Optional[str] = Field(None, description="任务描述")
    deadline: datetime = Field(..., description="截止时间")
    started_time: Optional[datetime] = Field(None, description="发布时间，None表示立即发布")
    template_id: int = Field(..., description="表单模板ID")
    mail_subject: str = Field(..., description="邮件标题")
    mail_content: str = Field(..., description="邮件正文")
    teacher_ids: List[int] = Field(..., min_length=1, description="目标教师ID列表")


class UpdateTaskRequest(BaseModel):
    """更新任务请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    deadline: Optional[datetime] = None
    started_time: Optional[datetime] = None
    template_id: Optional[int] = None
    mail_subject: Optional[str] = None
    mail_content: Optional[str] = None
    teacher_ids: Optional[List[int]] = None


# ==================== API 路由 ====================

@router.get("/list", response_model=List[TaskListItem])
async def get_task_list(
    current_user: Secretary = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    获取任务列表
    包含：任务基本信息、模板名称、回复统计
    """
    tasks = db.query(CollectTask).filter(
        CollectTask.created_by == current_user.id
    ).order_by(CollectTask.created_at.desc()).all()

    result = []
    for task in tasks:
        # 检查并更新状态
        check_task_status(task, db)
        
        # 获取模板名称
        template = db.query(TemplateForm).filter(
            TemplateForm.id == task.template_id
        ).first()

        # 统计总教师数
        total_count = db.query(CollectTaskTarget).filter(
            CollectTaskTarget.task_id == task.id
        ).count()

        # 统计已回复人数
        replied_count = db.query(func.count(func.distinct(ReceivedEmail.from_tea_id))).filter(
            ReceivedEmail.task_id == task.id
        ).scalar() or 0

        result.append(TaskListItem(
            id=task.id,
            name=task.name,
            started_time=ensure_utc(task.started_time),
            deadline=ensure_utc(task.deadline),
            template_name=template.name if template else "未知模板",
            replied_count=replied_count,
            total_count=total_count,
            status=task.status.value,
            created_at=ensure_utc(task.created_at)
        ))

    return result


@router.get("/{task_id}", response_model=TaskDetailResponse)
async def get_task_detail(
    task_id: int,
    current_user: Secretary = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    获取任务详情
    """
    task = db.query(CollectTask).filter(
        CollectTask.id == task_id,
        CollectTask.created_by == current_user.id
    ).first()

    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

    # 检查状态
    check_task_status(task, db)

    template = db.query(TemplateForm).filter(TemplateForm.id == task.template_id).first()
    target_teacher_ids = db.query(CollectTaskTarget.teacher_id).filter(CollectTaskTarget.task_id == task_id).all()
    teacher_ids = [t[0] for t in target_teacher_ids]
    replied_teacher_ids = set([t[0] for t in db.query(ReceivedEmail.from_tea_id).filter(ReceivedEmail.task_id == task_id).distinct().all()])
    teachers = db.query(Teacher).filter(Teacher.id.in_(teacher_ids)).all()

    teacher_list = [
        TeacherDetail(
            id=teacher.id,
            name=teacher.name,
            email=teacher.email,
            has_replied=teacher.id in replied_teacher_ids
        )
        for teacher in teachers
    ]
    teacher_list.sort(key=lambda x: (x.has_replied, x.name))

    mail_subject = None
    mail_content = None
    if task.mail_content_template:
        mail_subject = task.mail_content_template.get('subject')
        mail_content = task.mail_content_template.get('content')

    return TaskDetailResponse(
        id=task.id,
        name=task.name,
        description=task.description,
        started_time=ensure_utc(task.started_time),
        deadline=ensure_utc(task.deadline),
        template_id=task.template_id,
        template_name=template.name if template else "未知模板",
        mail_subject=mail_subject,
        mail_content=mail_content,
        status=task.status.value,
        teachers=teacher_list
    )


@router.post("/create")
async def create_task(
    request: CreateTaskRequest,
    current_user: Secretary = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    创建新任务
    """
    existing = db.query(CollectTask).filter(CollectTask.name == request.name).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="任务名称已存在")

    template = db.query(TemplateForm).filter(TemplateForm.id == request.template_id).first()
    if not template:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="模板不存在")

    teachers = db.query(Teacher).filter(Teacher.id.in_(request.teacher_ids)).all()
    if len(teachers) != len(request.teacher_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="部分教师不存在")

    now = get_utc_now()
    if request.started_time is None:
        started_time = now
        task_status = TaskStatus.ACTIVE
    else:
        started_time = ensure_utc(request.started_time)
        task_status = TaskStatus.DRAFT if started_time > now else TaskStatus.ACTIVE

    deadline = ensure_utc(request.deadline)

    new_task = CollectTask(
        name=request.name,
        description=request.description,
        started_time=started_time,
        deadline=deadline,
        template_id=request.template_id,
        status=task_status,
        created_by=current_user.id,
        mail_content_template={
            'subject': request.mail_subject,
            'content': request.mail_content
        },
        extra=None
    )

    try:
        db.add(new_task)
        db.flush()
        for teacher_id in request.teacher_ids:
            target = CollectTaskTarget(task_id=new_task.id, teacher_id=teacher_id)
            db.add(target)
        db.commit()
        return {"success": True, "message": "任务创建成功", "data": {"task_id": new_task.id}}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"创建任务失败：{str(e)}")


@router.put("/{task_id}")
async def update_task(
    task_id: int,
    request: UpdateTaskRequest,
    current_user: Secretary = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    更新任务（仅限未发布的任务）
    """
    task = db.query(CollectTask).filter(CollectTask.id == task_id, CollectTask.created_by == current_user.id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

    if task.status != TaskStatus.DRAFT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="只能编辑未发布的任务")

    if request.name is not None:
        existing = db.query(CollectTask).filter(CollectTask.name == request.name, CollectTask.id != task_id).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="任务名称已存在")
        task.name = request.name

    if request.deadline is not None:
        task.deadline = ensure_utc(request.deadline)

    if 'started_time' in request.model_dump(exclude_unset=True):
        now = get_utc_now()
        if request.started_time is None:
            task.started_time = now
            task.status = TaskStatus.ACTIVE
        else:
            task.started_time = ensure_utc(request.started_time)
            if task.started_time <= now:
                task.status = TaskStatus.ACTIVE
            else:
                task.status = TaskStatus.DRAFT

    if request.template_id is not None:
        template = db.query(TemplateForm).filter(TemplateForm.id == request.template_id).first()
        if not template:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="模板不存在")
        task.template_id = request.template_id

    if request.mail_subject or request.mail_content:
        if task.mail_content_template is None:
            task.mail_content_template = {}
        if request.mail_subject:
            task.mail_content_template['subject'] = request.mail_subject
        if request.mail_content:
            task.mail_content_template['content'] = request.mail_content

    if request.description is not None:
        task.description = request.description

    if request.teacher_ids is not None:
        db.query(CollectTaskTarget).filter(CollectTaskTarget.task_id == task_id).delete()
        for teacher_id in request.teacher_ids:
            target = CollectTaskTarget(task_id=task_id, teacher_id=teacher_id)
            db.add(target)

    try:
        db.commit()
        return {"success": True, "message": "任务更新成功"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"更新任务失败：{str(e)}")


@router.delete("/{task_id}")
async def delete_task(
    task_id: int,
    current_user: Secretary = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    删除任务（仅限未发布的任务）
    """
    task = db.query(CollectTask).filter(CollectTask.id == task_id, CollectTask.created_by == current_user.id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

    if task.status != TaskStatus.DRAFT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="只能删除未发布的任务")

    try:
        # 删除关联数据
        db.query(CollectTaskTarget).filter(CollectTaskTarget.task_id == task_id).delete()
        db.delete(task)
        db.commit()
        return {"success": True, "message": "任务已删除"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"删除任务失败：{str(e)}")


@router.post("/{task_id}/close")
async def close_task(
    task_id: int,
    current_user: Secretary = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    提前关闭任务并导出
    """
    task = db.query(CollectTask).filter(
        CollectTask.id == task_id,
        CollectTask.created_by == current_user.id
    ).first()

    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

    if task.status not in [TaskStatus.ACTIVE, TaskStatus.NEEDS_REAGGREGATION]:
        # 允许 ACTIVE 或 NEEDS_REAGGREGATION 状态下关闭/重新关闭
        pass

    # 1. 设置为 CLOSED
    task.status = TaskStatus.CLOSED
    db.add(task)
    db.commit()

    # 2. 执行汇总
    try:
        perform_aggregation(db, task, current_user.id)
        # 3. 设置为 AGGREGATED
        task.status = TaskStatus.AGGREGATED
        db.add(task)
        db.commit()
        return {"success": True, "message": "任务已关闭并完成汇总"}
    except Exception as e:
        # 汇总失败，保持 CLOSED
        return {"success": False, "message": f"任务已关闭，但汇总失败: {str(e)}"}


@router.post("/{task_id}/publish")
async def publish_task(
    task_id: int,
    current_user: Secretary = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    一键发布任务
    """
    task = db.query(CollectTask).filter(CollectTask.id == task_id, CollectTask.created_by == current_user.id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    if task.status != TaskStatus.DRAFT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="只能发布未发布的任务")

    task.started_time = get_utc_now()
    task.status = TaskStatus.ACTIVE
    try:
        db.commit()
        return {"success": True, "message": "任务已发布"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"发布任务失败：{str(e)}")


@router.post("/{task_id}/aggregate")
async def aggregate_task(
    task_id: int,
    current_user: Secretary = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    手动触发汇总（适用于重新导出）
    """
    task = db.query(CollectTask).filter(CollectTask.id == task_id, CollectTask.created_by == current_user.id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

    try:
        result = perform_aggregation(db, task, current_user.id)
        
        # 无论之前是什么状态，汇总成功后都转为 AGGREGATED
        task.status = TaskStatus.AGGREGATED
        db.add(task)
        db.commit()
            
        return {"success": True, "message": "汇总成功", "data": result}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"汇总失败: {str(e)}")
