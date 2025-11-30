import os
from sqlalchemy.orm import Session
from backend.database.models import (
    CollectTask, CollectTaskTarget, Secretary, Teacher, 
    SentEmail, SentAttachment, EmailStatus, TaskStatus, TemplateForm
)
from backend.email_service import send_email
from backend.helper.excel_utils import generate_template_excel
from backend.utils.encryption import decrypt_value
from backend.storage_service import storage
from backend.utils import get_utc_now

def get_smtp_config(email_address: str):
    """Simple config guesser based on domain"""
    domain = email_address.split('@')[-1].lower()
    if "qq.com" in domain:
        return {'smtp_server': 'smtp.qq.com', 'smtp_port': 587}
    elif "163.com" in domain:
        return {'smtp_server': 'smtp.163.com', 'smtp_port': 465}
    elif "sina.com" in domain:
        return {'smtp_server': 'smtp.sina.com', 'smtp_port': 465}
    # Default
    return {'smtp_server': 'smtp.qq.com', 'smtp_port': 587}

def publish_task_emails(db: Session, task_id: int):
    """
    Sends emails to all targets of the task.
    """
    task = db.query(CollectTask).filter(CollectTask.id == task_id).first()
    if not task:
        print(f"Task {task_id} not found")
        return

    secretary = db.query(Secretary).filter(Secretary.id == task.created_by).first()
    if not secretary or not secretary.mail_auth_code:
        print(f"Secretary {task.created_by} has no auth code configured")
        return

    # Decrypt auth code
    try:
        auth_code = decrypt_value(secretary.mail_auth_code)
    except Exception as e:
        print(f"Failed to decrypt auth code for secretary {secretary.id}: {e}")
        return

    # Generate Excel Template
    try:
        # Get template name for filename
        template = db.query(TemplateForm).filter(TemplateForm.id == task.template_id).first()
        template_name = template.name if template else "template"
        
        # Generate with specific filename
        temp_excel_path = generate_template_excel(db, task.template_id, filename=f"{template_name}.xlsx")
    except Exception as e:
        print(f"Failed to generate template excel: {e}")
        return

    # Upload template to MinIO (as SentAttachment)
    # We upload it once and reuse it for all emails in this batch? 
    # Or create one SentAttachment record per email? 
    # Usually one attachment record per unique file is enough, but SentEmail links to SentAttachment 1:1 or N:1?
    # SentEmail has attachment_id. SentAttachment is the file.
    # Let's create one SentAttachment record for this task publication.
    
    file_name = f"{template_name}.xlsx"
    minio_path = f"minio://mailmerge/sent_attachment/task_{task.id}/{file_name}"
    
    try:
        uploaded_path = storage.upload(temp_excel_path, minio_path)
        file_size = os.path.getsize(temp_excel_path)
    except Exception as e:
        print(f"Failed to upload template to storage: {e}")
        os.remove(temp_excel_path)
        return

    # Create SentAttachment record
    sent_attachment = SentAttachment(
        file_path=uploaded_path,
        file_name=file_name,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        file_size=file_size
    )
    db.add(sent_attachment)
    db.flush()

    # Get targets
    targets = db.query(CollectTaskTarget).filter(CollectTaskTarget.task_id == task.id).all()
    
    smtp_config = get_smtp_config(secretary.email)
    
    mail_subject = task.mail_content_template.get('subject', f"Task: {task.name}")
    mail_body = task.mail_content_template.get('content', "Please fill the attached form.")

    for target in targets:
        teacher = db.query(Teacher).filter(Teacher.id == target.teacher_id).first()
        if not teacher or not teacher.email:
            continue

        # Prepare email content
        email_content = {
            "subject": mail_subject,
            "body": mail_body,
            "attachments": [temp_excel_path] # send_email expects local path
        }

        # Send Email
        print(f"Sending email to {teacher.name} ({teacher.email})...")
        result = send_email(
            sender_email=secretary.email,
            sender_password=auth_code,
            receiver_email=teacher.email,
            email_content=email_content,
            smtp_server=smtp_config['smtp_server'],
            smtp_port=smtp_config['smtp_port']
        )

        # Record SentEmail
        status = EmailStatus.SENT if result['success'] else EmailStatus.FAILED
        
        sent_email = SentEmail(
            task_id=task.id,
            from_sec_id=secretary.id,
            to_tea_id=teacher.id,
            sent_at=get_utc_now() if result['success'] else None,
            status=status,
            mail_content=email_content, # Store what was sent
            attachment_id=sent_attachment.id,
            extra={"error": result.get('message')} if not result['success'] else None
        )
        db.add(sent_email)
    
    db.commit()
    
    # Cleanup temp file
    if os.path.exists(temp_excel_path):
        os.remove(temp_excel_path)
