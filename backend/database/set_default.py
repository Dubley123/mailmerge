"""
set_default.py

Load default data (generate/insert) into the database and upload attachments to MinIO.
This is intentionally separated from the reset script so `--reset` only clears,
and `--set-default` will populate default data.
"""
import sys
import os
from pathlib import Path
import json
import hashlib
from sqlalchemy.pool import NullPool
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.database.models import (
    Department, Teacher, Secretary, TemplateForm, TemplateFormField,
    CollectTask, CollectTaskTarget, SentAttachment, SentEmail,
    ReceivedAttachment, ReceivedEmail,
    EmailStatus, TaskStatus
)
from backend.database.db_config import get_engine, get_session_factory
from backend.storage_service import ensure_minio_running
from backend.utils import ensure_utc
from backend.utils.encryption import encrypt_value
from backend.database.db_config import get_engine, get_session_factory
from backend.logger import get_logger

logger = get_logger(__name__)


def hash_password(password: str) -> str:
    """
    Simple password hashing (use bcrypt in production)
    
    Args:
        password: Plain text password
    
    Returns:
        Hashed password
    """
    return hashlib.sha256(password.encode()).hexdigest()


def validate_json_structure(data: dict) -> None:
    """
    Validate that JSON data uses correct table names
    
    Args:
        data: JSON data to validate
        
    Raises:
        ValueError: If old table names are found
    """
    # Check for old table names
    old_names = {'campaigns', 'campaign_targets', 'templates', 'template_fields'}
    found_old = old_names & set(data.keys())
    
    if found_old:
        raise ValueError(
            f"❌ JSON data contains old table names: {found_old}. "
            f"Please use new names: collect_tasks, collect_task_targets, "
            f"template_forms, template_form_fields"
        )
    
    # Check for old field names in emails
    if 'sent_emails' in data:
        for i, email in enumerate(data['sent_emails']):
            if 'campaign_id' in email:
                raise ValueError(
                    f"❌ sent_emails[{i}] contains old field 'campaign_id'. "
                    f"Use 'task_id' instead."
                )
    
    if 'received_emails' in data:
        for i, email in enumerate(data['received_emails']):
            if 'campaign_id' in email:
                raise ValueError(
                    f"❌ received_emails[{i}] contains old field 'campaign_id'. "
                    f"Use 'task_id' instead."
                )
    
    logger.info("JSON structure validation passed")

def load_default_data(session, data_file: str):
    """
    Load default data from JSON file into database
    
    Args:
        session: SQLAlchemy session
        data_file: Path to JSON file
    """
    logger.info(f"Loading default data from {data_file}...")
    
    # Read JSON file
    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Validate JSON structure (ensure no old table/field names)
    validate_json_structure(data)
    
    # Department ID mapping
    dept_id_map = {}
    
    # 1. Load Departments
    if 'departments' in data:
        logger.info("Loading departments...")
        for dept_data in data['departments']:
            dept = Department(
                name=dept_data['name'],
            )
            session.add(dept)
            session.flush()  # Get the ID
            dept_id_map[dept_data['name']] = dept.id
        session.commit()
        logger.info(f"Loaded {len(data['departments'])} departments")
    
    # 2. Load Teachers
    teacher_id_map = {}
    if 'teachers' in data:
        logger.info("Loading teachers...")
        for teacher_data in data['teachers']:
            dept_name = teacher_data.get('department_name')
            dept_id = dept_id_map.get(dept_name)
            
            if dept_id is None:
                logger.warning(f"Department '{dept_name}' not found for teacher {teacher_data['name']}")
                continue
            
            teacher = Teacher(
                id=teacher_data['id'],  # 工号，手动指定
                name=teacher_data['name'],
                department_id=dept_id,
                email=teacher_data['email'],
                phone=teacher_data.get('phone'),
                title=teacher_data.get('title'),
                office=teacher_data.get('office'),
            )
            session.add(teacher)
            session.flush()
            teacher_id_map[teacher.id] = teacher.id
        session.commit()
        logger.info(f"Loaded {len(data['teachers'])} teachers")
    
    # 3. Load Secretaries
    secretary_id_map = {}
    if 'secretaries' in data:
        logger.info("Loading secretaries...")
        for sec_data in data['secretaries']:
            dept_name = sec_data.get('department_name')
            dept_id = dept_id_map.get(dept_name)
            
            if dept_id is None:
                logger.warning(f"Department '{dept_name}' not found for secretary {sec_data['name']}")
                continue
            
            secretary = Secretary(
                id=sec_data['id'],  # 工号，手动指定
                name=sec_data['name'],
                department_id=dept_id,
                username=sec_data['username'],
                account=sec_data['account'],
                password_hash=hash_password(sec_data.get('password', '123456')),
                email=sec_data['email'],
                mail_auth_code=encrypt_value(sec_data.get('mail_auth_code')) if sec_data.get('mail_auth_code') else None,
                phone=sec_data.get('phone'),
            )
            session.add(secretary)
            session.flush()
            secretary_id_map[secretary.id] = secretary.id
        session.commit()
        logger.info(f"Loaded {len(data['secretaries'])} secretaries")
    
    # 4. Load Template Forms
    template_id_map = {}
    if 'template_forms' in data:
        logger.info("Loading template forms...")
        for idx, tmpl_data in enumerate(data['template_forms']):
            template = TemplateForm(
                name=tmpl_data['name'],
                description=tmpl_data.get('description'),
                created_by=tmpl_data.get('created_by'),  # 直接使用secretary ID
            )
            session.add(template)
            session.flush()  # 获取自动生成的ID
            template_id_map[idx] = template.id
        session.commit()
        logger.info(f"Loaded {len(data['template_forms'])} template forms")
    
    # 5. Load Template Form Fields
    if 'template_form_fields' in data:
        logger.info("Loading template form fields...")
        for field_data in data['template_form_fields']:
            # Get form_id from form_index
            form_index = field_data.get('form_index', 0)
            if form_index not in template_id_map:
                logger.warning(f"form_index {form_index} not found, skipping field")
                continue
            
            form_id = template_id_map[form_index]
            
            # Strict new-format: require `validation_rule` key in the field data
            if 'validation_rule' not in field_data:
                raise ValueError("template_form_fields must include 'validation_rule' for each field under new schema. Please update default data to use `validation_rule`.")
            # Do not allow legacy keys: force strict new schema
            if 'data_type' in field_data or 'required' in field_data:
                raise ValueError("Legacy fields 'data_type' or 'required' are not allowed under new schema. Use 'validation_rule' instead.")
            validation_rule = field_data.get('validation_rule')
            field = TemplateFormField(
                form_id=form_id,
                ord=field_data.get('ord', 0),
                display_name=field_data['display_name'],
                validation_rule=validation_rule,
            )
            session.add(field)
        session.commit()
        logger.info(f"Loaded {len(data['template_form_fields'])} template fields")
    
    # 6. Load Collect Tasks
    task_id_map = {}
    if 'collect_tasks' in data:
        logger.info("Loading collect tasks...")
        for idx, task_data in enumerate(data['collect_tasks']):
            # Get template_id from first template
            if 0 not in template_id_map:
                logger.warning("No template form created yet, skipping tasks")
                break
            
            template_id = template_id_map[0]
            
            # Convert string status to enum
            status_str = task_data.get('status', 'DRAFT')
            status = TaskStatus[status_str] if hasattr(TaskStatus, status_str) else TaskStatus.DRAFT
            
            # Parse datetime strings
            started_time = None
            deadline = None
            if task_data.get('started_time'):
                started_time = ensure_utc(datetime.fromisoformat(task_data['started_time'].replace('Z', '+00:00')))
            if task_data.get('deadline'):
                deadline = ensure_utc(datetime.fromisoformat(task_data['deadline'].replace('Z', '+00:00')))
            
            task = CollectTask(
                name=task_data['name'],
                description=task_data.get('description'),
                started_time=started_time,
                deadline=deadline,
                template_id=template_id,
                mail_content_template=task_data.get('mail_content_template', {}),
                status=status,
                created_by=task_data.get('created_by'),  # 直接使用secretary ID
            )
            session.add(task)
            session.flush()  # 获取自动生成的task ID
            task_id_map[idx] = task.id
            
            # Load targets for this task
            if 'targets' in task_data:
                for target_data in task_data['targets']:
                    teacher_id = target_data.get('teacher_id')
                    if teacher_id not in teacher_id_map:
                        logger.warning(f"teacher_id {teacher_id} not found, skipping target")
                        continue
                    
                    target = CollectTaskTarget(
                        task_id=task.id,
                        teacher_id=teacher_id
                    )
                    session.add(target)
        
        session.commit()
        logger.info(f"Loaded {len(data['collect_tasks'])} collect tasks")
    
    # 7. Load Sent Attachments
    sent_attach_id_map = {}
    if 'sent_attachments' in data:
        logger.info("Loading sent attachments...")
        
        # Get attachment directory
        attachment_dir = str(Path(data_file).parent / "attachment")
        
        for idx, attach_data in enumerate(data['sent_attachments']):
            file_path = attach_data['file_path']
            file_name = attach_data.get('file_name')
            
            # Upload file to storage if it exists locally
            if file_name and os.path.exists(attachment_dir):
                local_file = os.path.join(attachment_dir, file_name)
                if os.path.exists(local_file):
                    try:
                        from backend.storage_service import storage
                        # Use the file_path from JSON as target path
                        storage.upload(local_file, file_path)
                        logger.info(f"Uploaded: {file_name} -> {file_path}")
                    except Exception as e:
                        error_msg = f"Failed to upload {file_name}: {e}"
                        logger.error(error_msg)
                        raise RuntimeError(error_msg) from e
            
            attachment = SentAttachment(
                file_path=file_path,
                file_name=file_name,
                content_type=attach_data.get('content_type'),
                file_size=attach_data.get('file_size'),
            )
            session.add(attachment)
            session.flush()
            sent_attach_id_map[idx] = attachment.id
        session.commit()
        logger.info(f"Loaded {len(data['sent_attachments'])} sent attachments")
    
    # 9. Load Sent Emails
    if 'sent_emails' in data:
        logger.info("Loading sent emails...")
        # 默认使用第一个task和第一个attachment
        task_id = task_id_map.get(0) if task_id_map else None
        attachment_id = sent_attach_id_map.get(0) if sent_attach_id_map else None
        
        for email_data in data['sent_emails']:
            # Convert status string to enum
            status_str = email_data.get('status', 'queued')
            status = EmailStatus[status_str] if hasattr(EmailStatus, status_str) else EmailStatus.QUEUED
            
            # Parse datetime
            sent_at = None
            if email_data.get('sent_at'):
                sent_at = ensure_utc(datetime.fromisoformat(email_data['sent_at'].replace('Z', '+00:00')))
            
            email = SentEmail(
                task_id=task_id,  # 使用刚创建的task ID
                from_sec_id=email_data.get('from_sec_id'),  # 直接使用secretary ID
                to_tea_id=email_data.get('to_tea_id'),  # 直接使用teacher ID
                sent_at=sent_at,
                status=status,
                retry_count=email_data.get('retry_count', 0),
                message_id=email_data.get('message_id'),
                mail_content=email_data.get('mail_content', {}),
                attachment_id=attachment_id,  # 使用刚创建的attachment ID
            )
            session.add(email)
        session.commit()
        logger.info(f"Loaded {len(data['sent_emails'])} sent emails")
    
    # 10. Load Received Attachments
    recv_attach_id_map = {}
    if 'received_attachments' in data:
        logger.info("Loading received attachments...")
        
        # Get attachment directory
        attachment_dir = str(Path(data_file).parent / "attachment")
        
        for idx, attach_data in enumerate(data['received_attachments']):
            file_path = attach_data['file_path']
            file_name = attach_data.get('file_name')
            
            # Upload file to storage if it exists locally
            if file_name and os.path.exists(attachment_dir):
                local_file = os.path.join(attachment_dir, file_name)
                if os.path.exists(local_file):
                    try:
                        from backend.storage_service import storage
                        # Use the file_path from JSON as target path
                        storage.upload(local_file, file_path)
                        logger.info(f"Uploaded: {file_name} -> {file_path}")
                    except Exception as e:
                        error_msg = f"Failed to upload {file_name}: {e}"
                        logger.error(error_msg)
                        raise RuntimeError(error_msg) from e
            
            attachment = ReceivedAttachment(
                file_path=file_path,
                file_name=file_name,
                content_type=attach_data.get('content_type'),
                file_size=attach_data.get('file_size'),
            )
            session.add(attachment)
            session.flush()
            recv_attach_id_map[idx] = attachment.id
        session.commit()
        logger.info(f"Loaded {len(data['received_attachments'])} received attachments")
    
    # 11. Load Received Emails
    if 'received_emails' in data:
        logger.info("Loading received emails...")
        # 默认使用第一个task
        task_id = task_id_map.get(0) if task_id_map else None
        
        for idx, email_data in enumerate(data['received_emails']):
            # Parse datetime
            received_at = ensure_utc(datetime.fromisoformat(email_data['received_at'].replace('Z', '+00:00')))
            
            # 每个email对应不同的attachment
            attachment_id = recv_attach_id_map.get(idx) if idx in recv_attach_id_map else None
            
            email = ReceivedEmail(
                task_id=task_id,  # 使用刚创建的task ID
                from_tea_id=email_data.get('from_tea_id'),  # 直接使用teacher ID
                to_sec_id=email_data.get('to_sec_id'),  # 直接使用secretary ID
                received_at=received_at,
                message_id=email_data.get('message_id'),
                mail_content=email_data.get('mail_content', {}),
                attachment_id=attachment_id,  # 使用对应的attachment ID
                is_aggregated=email_data.get('is_aggregated', False),
            )
            session.add(email)
        session.commit()
        logger.info(f"Loaded {len(data['received_emails'])} received emails")
    
    logger.info("All default data loaded successfully")

def set_default(data_file: str = None):
    if data_file is None:
        data_file = str(Path(__file__).parent / "default_data" / "default_data.json")

    # Note: We assume MinIO is running and bucket exists (checked by caller)
    
    # Create engine and session
    engine = get_engine(echo=False, poolclass=NullPool)
    SessionLocal = get_session_factory(engine)
    session = SessionLocal()

    if data_file and os.path.exists(data_file):
        try:
            load_default_data(session, data_file)
            logger.info("Default data inserted successfully.")
        except Exception as e:
            logger.error(f"Error loading default data: {e}")
            session.rollback()
            raise
        finally:
            session.close()
    else:
        logger.error(f"No default data file found at: {data_file}")


if __name__ == '__main__':
    # Simple CLI: python set_default.py [path_to_json]
    data_file = sys.argv[1] if len(sys.argv) > 1 else None
    set_default(data_file)
