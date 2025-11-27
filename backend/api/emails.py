"""
邮件相关 API 路由
处理邮件发送、接收、查看等操作
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List

from backend.database.db_config import get_db_session
from backend.database.models import SentEmail, ReceivedEmail, Secretary
from backend.api.auth import get_current_user

router = APIRouter()


# ==================== Pydantic 模型 ====================

class EmailResponse(BaseModel):
    """邮件响应"""
    id: int
    subject: str
    status: str


# ==================== API 路由 ====================

@router.get("/sent")
async def get_sent_emails(
    current_user: Secretary = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    获取已发送邮件列表
    """
    emails = db.query(SentEmail).filter(
        SentEmail.secretary_id == current_user.id
    ).limit(10).all()
    
    return [
        {
            "id": email.id,
            "subject": email.subject,
            "status": email.status.value,
            "sent_at": email.sent_at
        }
        for email in emails
    ]


@router.get("/received")
async def get_received_emails(
    current_user: Secretary = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    获取已接收邮件列表
    """
    emails = db.query(ReceivedEmail).filter(
        ReceivedEmail.secretary_id == current_user.id
    ).limit(10).all()
    
    return [
        {
            "id": email.id,
            "subject": email.subject,
            "received_at": email.received_at
        }
        for email in emails
    ]
