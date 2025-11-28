"""
邮件相关 API 路由
处理邮件发送、接收、查看等操作
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from datetime import timezone
from backend.utils import ensure_utc

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
        SentEmail.from_sec_id == current_user.id
    ).limit(10).all()
    
    return [
        {
            "id": email.id,
            "subject": email.mail_content.get('subject') if email.mail_content else "无标题",
            "status": email.status.value,
            "sent_at": ensure_utc(email.sent_at)
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
        ReceivedEmail.to_sec_id == current_user.id
    ).limit(10).all()
    
    return [
        {
            "id": email.id,
            "subject": email.mail_content.get('subject') if email.mail_content else "无标题",
            "received_at": ensure_utc(email.received_at)
        }
        for email in emails
    ]
