from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime

from backend.database.db_config import get_db_session
from backend.api.auth import get_current_user
from backend.database.models import (
    CollectTask, SentEmail, ReceivedEmail, Teacher, Secretary, 
    SentAttachment, ReceivedAttachment
)

router = APIRouter()

# --- Pydantic Models ---

class TaskFolder(BaseModel):
    id: int
    name: str
    description: Optional[str]
    sent_count: int
    received_count: int
    created_at: datetime

class EmailAttachment(BaseModel):
    id: int
    file_name: str
    file_size: Optional[int]
    content_type: Optional[str]
    # In a real app, we would generate a presigned URL here
    # For now, we might just return the ID or a download link path
    download_url: str 

class EmailItem(BaseModel):
    id: int
    subject: str
    sender_name: str
    sender_email: str
    recipient_name: str
    recipient_email: str
    timestamp: datetime
    snippet: str
    has_attachment: bool
    attachment: Optional[EmailAttachment] = None
    body: Optional[str] = None # Included for detail view, might be truncated in list

# --- Endpoints ---

@router.get("/tasks", response_model=List[TaskFolder])
def get_mailbox_tasks(
    db: Session = Depends(get_db_session),
    current_user: Secretary = Depends(get_current_user)
):
    """
    Get all tasks for the current secretary with email counts.
    """
    tasks = db.query(CollectTask).filter(CollectTask.created_by == current_user.id).all()
    
    result = []
    for task in tasks:
        sent_count = db.query(func.count(SentEmail.id)).filter(SentEmail.task_id == task.id).scalar()
        received_count = db.query(func.count(ReceivedEmail.id)).filter(ReceivedEmail.task_id == task.id).scalar()
        
        result.append(TaskFolder(
            id=task.id,
            name=task.name,
            description=task.description,
            sent_count=sent_count,
            received_count=received_count,
            created_at=task.created_at
        ))
    
    return result

@router.get("/tasks/{task_id}/emails", response_model=List[EmailItem])
def get_task_emails(
    task_id: int,
    type: str = Query(..., regex="^(sent|received)$"),
    db: Session = Depends(get_db_session),
    current_user: Secretary = Depends(get_current_user)
):
    """
    Get emails for a specific task.
    """
    # Verify task ownership
    task = db.query(CollectTask).filter(CollectTask.id == task_id, CollectTask.created_by == current_user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    emails = []
    
    if type == "sent":
        # Query Sent Emails
        sent_emails = db.query(SentEmail).filter(SentEmail.task_id == task_id).order_by(desc(SentEmail.sent_at)).all()
        
        for email in sent_emails:
            # Resolve Recipient (Teacher)
            teacher = db.query(Teacher).filter(Teacher.id == email.to_tea_id).first()
            recipient_name = teacher.name if teacher else "Unknown"
            recipient_email = teacher.email if teacher else "Unknown"
            
            # Resolve Attachment
            att_data = None
            if email.attachment_id:
                att = db.query(SentAttachment).filter(SentAttachment.id == email.attachment_id).first()
                if att:
                    att_data = EmailAttachment(
                        id=att.id,
                        file_name=att.file_name or "attachment",
                        file_size=att.file_size,
                        content_type=att.content_type,
                        download_url=f"/api/files/sent/{att.id}" # Placeholder URL structure
                    )

            # Parse Content
            content = email.mail_content or {}
            subject = content.get("subject", f"Task: {task.name}")
            body = content.get("body", "No content")
            snippet = body[:100] + "..." if len(body) > 100 else body

            emails.append(EmailItem(
                id=email.id,
                subject=subject,
                sender_name=current_user.name, # Sent by me
                sender_email=current_user.email,
                recipient_name=recipient_name,
                recipient_email=recipient_email,
                timestamp=email.sent_at or email.created_at,
                snippet=snippet,
                has_attachment=att_data is not None,
                attachment=att_data,
                body=body
            ))

    else:
        # Query Received Emails
        received_emails = db.query(ReceivedEmail).filter(ReceivedEmail.task_id == task_id).order_by(desc(ReceivedEmail.received_at)).all()
        
        for email in received_emails:
            # Resolve Sender (Teacher)
            teacher = db.query(Teacher).filter(Teacher.id == email.from_tea_id).first()
            sender_name = teacher.name if teacher else "Unknown"
            sender_email = teacher.email if teacher else "Unknown"
            
            # Resolve Attachment
            att_data = None
            if email.attachment_id:
                att = db.query(ReceivedAttachment).filter(ReceivedAttachment.id == email.attachment_id).first()
                if att:
                    att_data = EmailAttachment(
                        id=att.id,
                        file_name=att.file_name or "attachment",
                        file_size=att.file_size,
                        content_type=att.content_type,
                        download_url=f"/api/files/received/{att.id}" # Placeholder URL structure
                    )

            # Parse Content
            content = email.mail_content or {}
            subject = content.get("subject", f"Re: {task.name}")
            body = content.get("body", "No content")
            snippet = body[:100] + "..." if len(body) > 100 else body

            emails.append(EmailItem(
                id=email.id,
                subject=subject,
                sender_name=sender_name,
                sender_email=sender_email,
                recipient_name=current_user.name, # Received by me
                recipient_email=current_user.email,
                timestamp=email.received_at,
                snippet=snippet,
                has_attachment=att_data is not None,
                attachment=att_data,
                body=body
            ))
            
    return emails
