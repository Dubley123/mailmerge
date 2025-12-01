import os
import re
import pandas as pd
from sqlalchemy.orm import Session
from backend.database.models import (
    Secretary, Teacher, ReceivedEmail, ReceivedAttachment, 
    SentEmail, CollectTask, TaskStatus, TemplateForm, TemplateFormField
)
from backend.email_service import fetch_email
from email.utils import parsedate_to_datetime
from datetime import timezone
from backend.utils.encryption import decrypt_value
from backend.storage_service import storage
from backend.utils import get_utc_now
from backend.logger import get_logger

module_logger = get_logger(__name__)

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

def fetch_and_process_emails(db: Session, since_ts=None, logger=None):
    """
    Fetch unread emails for all secretaries and process them.
    Returns (max_seen_ts, total_processed_count)
    """
    if logger is None:
        logger = module_logger.info

    secretaries = db.query(Secretary).filter(Secretary.mail_auth_code != None).all()
    
    max_seen_ts = None
    total_processed = 0
    
    for secretary in secretaries:
        try:
            # pass since_ts to process for filtering; returns (latest timestamp seen, count processed)
            sec_max, count = process_secretary_emails(db, secretary, since_ts, logger)
            total_processed += count
            
            if sec_max:
                if max_seen_ts is None or sec_max > max_seen_ts:
                    max_seen_ts = sec_max
        except Exception as e:
            msg = f"Error processing emails for secretary {secretary.email}: {e}"
            logger(msg)

    return max_seen_ts, total_processed

def process_secretary_emails(db: Session, secretary: Secretary, since_ts=None, logger=None):
    if logger is None:
        logger = module_logger.info

    try:
        auth_code = decrypt_value(secretary.mail_auth_code)
    except Exception:
        return None, 0

    imap_config = get_imap_config(secretary.email)
    
    # Fetch emails
    result = fetch_email(
        email_address=secretary.email,
        email_password=auth_code,
        imap_server=imap_config['imap_server'],
        imap_port=imap_config['imap_port'],
        only_unread=False
    )
    
    if not result['success']:
        msg = f"Failed to fetch emails for {secretary.email}: {result['message']}"
        logger(msg)
        return None, 0

    latest_ts = None
    processed_count = 0
    
    for email_data in result['emails']:
        # Parse date header to datetime
        date_str = email_data.get('date')
        email_dt = None
        try:
            if date_str:
                email_dt = parsedate_to_datetime(date_str)
                if email_dt and email_dt.tzinfo is None:
                    email_dt = email_dt.replace(tzinfo=timezone.utc)
                # normalize to UTC
                if email_dt:
                    email_dt = email_dt.astimezone(timezone.utc)
        except Exception:
            email_dt = None

        # Update latest_ts seen
        if email_dt:
            if latest_ts is None or email_dt > latest_ts:
                latest_ts = email_dt

        # If since_ts provided, skip emails on/before since_ts
        if since_ts and email_dt:
            try:
                if email_dt <= since_ts:
                    # skip old email
                    continue
            except Exception:
                pass

        try:
            process_single_email(db, secretary, email_data, logger)
            processed_count += 1
        except Exception as e:
            msg = f"Error processing email {email_data.get('id')}: {e}"
            logger(msg)

    return latest_ts, processed_count

def process_single_email(db: Session, secretary: Secretary, email_data: dict, logger=None):
    if logger is None:
        logger = module_logger.info

    # 1. Identify Teacher
    sender_str = email_data.get('from', '')
    # Extract email from "Name <email>" or just "email"
    email_match = re.search(r'<([^>]+)>', sender_str)
    sender_email = email_match.group(1) if email_match else sender_str.strip()
    
    teacher = db.query(Teacher).filter(Teacher.email == sender_email).first()
    if not teacher:
        msg = f"Ignored email from unknown teacher: {sender_email}"
        logger(msg)
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
                msg = f"Identified task {task.id} by subject match: '{task.name}' in '{subject}'"
                logger(msg)
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
                            msg = f"Identified task {task.id} by Excel headers"
                            logger(msg)
                            break
                except Exception as e:
                    msg = f"Failed to read Excel headers for identification: {e}"
                    logger(msg)

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
            msg = f"Failed to upload attachment: {e}"
            logger(msg)

    if not task_id:
        msg = f"Could not identify task for email from {sender_email}. Saved with task_id=None."
        logger(msg)

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
        msg = f"Processed email from teacher {teacher_id} for task {task_id}"
        logger(msg)
