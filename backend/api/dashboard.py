"""
Dashboard API 路由
提供首页概览数据统计
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from pydantic import BaseModel
from typing import Dict, Optional

from backend.database.db_config import get_db_session
from backend.database.models import (
    Secretary, Department, CollectTask, 
    SentEmail, ReceivedEmail, Aggregation,
    TaskStatus
)
from backend.api.auth import get_current_user

router = APIRouter()


# ==================== Pydantic 模型 ====================

class PersonalInfo(BaseModel):
    """个人信息"""
    name: str
    employee_id: int
    department_name: str
    email: str
    phone: Optional[str] = None
    username: str
    account: str


class TaskStats(BaseModel):
    """任务统计"""
    total: int
    draft: int
    active: int
    closed: int
    aggregated: int
    needs_reaggregation: int


class EmailStats(BaseModel):
    """邮件统计"""
    sent_total: int
    received_total: int
    aggregated: int
    not_aggregated: int
    aggregation_count: int


class DashboardData(BaseModel):
    """Dashboard 完整数据"""
    personal_info: PersonalInfo
    task_stats: TaskStats
    email_stats: EmailStats


# ==================== API 端点 ====================

@router.get("/overview", response_model=DashboardData)
async def get_dashboard_overview(
    current_user: Secretary = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    获取首页概览数据
    包括：个人信息、任务统计、邮件统计
    """
    # 获取当前用户 ID
    secretary_id = current_user.id

    # 1. 获取个人信息
    secretary = db.query(Secretary).filter(Secretary.id == secretary_id).first()
    if not secretary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户信息不存在"
        )

    department = db.query(Department).filter(
        Department.id == secretary.department_id
    ).first()

    personal_info = PersonalInfo(
        name=secretary.name,
        employee_id=secretary.id,
        department_name=department.name if department else "未知院系",
        email=secretary.email,
        phone=secretary.phone,
        username=secretary.username,
        account=secretary.account
    )

    # 2. 获取任务统计
    task_query = db.query(CollectTask).filter(CollectTask.created_by == secretary_id)
    
    total_tasks = task_query.count()
    draft_tasks = task_query.filter(CollectTask.status == TaskStatus.DRAFT).count()
    active_tasks = task_query.filter(CollectTask.status == TaskStatus.ACTIVE).count()
    closed_tasks = task_query.filter(CollectTask.status == TaskStatus.CLOSED).count()
    aggregated_tasks = task_query.filter(CollectTask.status == TaskStatus.AGGREGATED).count()
    needs_reaggregation_tasks = task_query.filter(CollectTask.status == TaskStatus.NEEDS_REAGGREGATION).count()

    task_stats = TaskStats(
        total=total_tasks,
        draft=draft_tasks,
        active=active_tasks,
        closed=closed_tasks,
        aggregated=aggregated_tasks,
        needs_reaggregation=needs_reaggregation_tasks
    )

    # 3. 获取邮件统计
    sent_total = db.query(SentEmail).filter(
        SentEmail.from_sec_id == secretary_id
    ).count()

    received_total = db.query(ReceivedEmail).filter(
        ReceivedEmail.to_sec_id == secretary_id
    ).count()

    aggregated = db.query(ReceivedEmail).filter(
        and_(
            ReceivedEmail.to_sec_id == secretary_id,
            ReceivedEmail.is_aggregated == True
        )
    ).count()

    not_aggregated = db.query(ReceivedEmail).filter(
        and_(
            ReceivedEmail.to_sec_id == secretary_id,
            ReceivedEmail.is_aggregated == False
        )
    ).count()

    # 统计汇总表数量
    aggregation_count = db.query(Aggregation).filter(
        Aggregation.generated_by == secretary_id
    ).count()

    email_stats = EmailStats(
        sent_total=sent_total,
        received_total=received_total,
        aggregated=aggregated,
        not_aggregated=not_aggregated,
        aggregation_count=aggregation_count
    )

    # 返回完整数据
    return DashboardData(
        personal_info=personal_info,
        task_stats=task_stats,
        email_stats=email_stats
    )
