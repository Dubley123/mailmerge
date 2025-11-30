import os
import re
import pandas as pd
from sqlalchemy.orm import Session
from backend.database.models import (
    Secretary, Teacher, ReceivedEmail, ReceivedAttachment, 
    SentEmail, CollectTask, TaskStatus, TemplateForm, TemplateFormField
)
from backend.email_service import fetch_email
from backend.utils.encryption import decrypt_value
from backend.storage_service import storage
from backend.utils import get_utc_now

def get_imap_config(email_address: str):
    """Simple config guesser based on domain"""
    domain = email_address.split('@')[-1].lower()
    if "qq.com" in domain:
        return {'imap_server': 'imap.qq.com', 'imap_port': 993}
    elif "163.com" in domain:
        return {'imap_server': 'imap.163.com', 'imap_port': 993}
    elif "sina.com" in domain:
        return {'imap_server': 'imap.sina.com', 'imap_port': 993}
    # Default
    return {'imap_server': 'imap.qq.com', 'imap_port': 993}

def fetch_and_process_emails(db: Session):
    """
    Fetch unread emails for all secretaries and process them.
    """
    secretaries = db.query(Secretary).filter(Secretary.mail_auth_code != None).all()
    
    for secretary in secretaries:
        try:
            process_secretary_emails(db, secretary)
        except Exception as e:
            print(f"Error processing emails for secretary {secretary.email}: {e}")

def process_secretary_emails(db: Session, secretary: Secretary):
    try:
        auth_code = decrypt_value(secretary.mail_auth_code)
    except Exception:
        return

    imap_config = get_imap_config(secretary.email)
    
    # Fetch emails
    result = fetch_email(
        email_address=secretary.email,
        email_password=auth_code,
        imap_server=imap_config['imap_server'],
        imap_port=imap_config['imap_port'],
        only_unread=True
    )
    
    if not result['success']:
        print(f"Failed to fetch emails for {secretary.email}: {result['message']}")
        return

    for email_data in result['emails']:
        try:
            process_single_email(db, secretary, email_data)
        except Exception as e:
            print(f"Error processing email {email_data.get('id')}: {e}")

def process_single_email(db: Session, secretary: Secretary, email_data: dict):
    # 1. Identify Teacher
    sender_str = email_data.get('from', '')
    # Extract email from "Name <email>" or just "email"
    email_match = re.search(r'<([^>]+)>', sender_str)
    sender_email = email_match.group(1) if email_match else sender_str.strip()
    
    teacher = db.query(Teacher).filter(Teacher.email == sender_email).first()
    if not teacher:
        print(f"Ignored email from unknown teacher: {sender_email}")
        return
    
    teacher_id = teacher.id

    # 2. Identify Task
    task_id = None
    attachment_id = None

    # Get all relevant tasks for this secretary
    tasks = db.query(CollectTask).filter(
        CollectTask.created_by == secretary.id,
        CollectTask.status.in_([TaskStatus.ACTIVE, TaskStatus.DRAFT, TaskStatus.CLOSED, TaskStatus.AGGREGATED, TaskStatus.NEEDS_REAGGREGATION])
    ).all()

    # 2a. Check Subject for Task Name
    subject = email_data.get('subject', '')
    if subject:
        for task in tasks:
            if task.name and task.name in subject:
                task_id = task.id
                print(f"Identified task {task.id} by subject match: '{task.name}' in '{subject}'")
                break
    
    # 2b. Process Attachment (and check headers if task_id is still None)
    if email_data.get('attachments'):
        # We only handle the first attachment for now
        local_path = email_data['attachments'][0]
        file_name = os.path.basename(local_path)
        
        # Check if it is an Excel file
        if file_name.lower().endswith('.xlsx') or file_name.lower().endswith('.xls'):
            # Only try to identify if not already identified
            if not task_id:
                try:
                    # Read headers from Excel
                    df = pd.read_excel(local_path, engine='openpyxl', nrows=0)
                    headers = set([str(col).strip() for col in df.columns])
                    
                    for task in tasks:
                        # Get template fields
                        template_fields = db.query(TemplateFormField).filter(
                            TemplateFormField.form_id == task.template_id
                        ).all()
                        template_headers = set([f.display_name.strip() for f in template_fields])
                        
                        # Check if headers match
                        if template_headers and template_headers.issubset(headers):
                            task_id = task.id
                            print(f"Identified task {task.id} by Excel headers")
                            break
                except Exception as e:
                    print(f"Failed to read Excel headers for identification: {e}")

        # Upload to MinIO
        # If task_id is None, we store it in a generic folder or keep it as is?
        # Let's store it in 'unknown_task' folder if task_id is None
        storage_task_id = task_id if task_id else "unknown"
        minio_path = f"minio://mailmerge/received_attachment/task_{storage_task_id}/{file_name}"
        
        try:
            uploaded_path = storage.upload(local_path, minio_path)
            file_size = os.path.getsize(local_path)
            
            # Create ReceivedAttachment
            att = ReceivedAttachment(
                file_path=uploaded_path,
                file_name=file_name,
                content_type="application/octet-stream",
                file_size=file_size
            )
            db.add(att)
            db.flush()
            attachment_id = att.id
            
            # Cleanup local file
            if os.path.exists(local_path):
                os.remove(local_path)
        except Exception as e:
            print(f"Failed to upload attachment: {e}")

    if not task_id:
        print(f"Could not identify task for email from {sender_email}. Saved with task_id=None.")

    # 3. Save ReceivedEmail
    received_email = ReceivedEmail(
        task_id=task_id,
        from_tea_id=teacher_id,
        to_sec_id=secretary.id,
        received_at=get_utc_now(), # Or parse email date
        message_id=email_data.get('message_id'),
        mail_content={
            "subject": email_data.get('subject'),
            "body": email_data.get('body')
        },
        attachment_id=attachment_id,
        is_aggregated=False
    )
    db.add(received_email)
    
    # 4. Update Task Status if needed
    if task_id:
        task = db.query(CollectTask).filter(CollectTask.id == task_id).first()
        if task and task.status == TaskStatus.AGGREGATED:
            task.status = TaskStatus.NEEDS_REAGGREGATION
            db.add(task)
        
    db.commit()
    if task_id:
        print(f"Processed email from teacher {teacher_id} for task {task_id}")

