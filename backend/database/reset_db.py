"""
Database Reset Script
Drops and recreates all tables, then loads default data
Clears and re-uploads MinIO attachments
"""
import sys
import os
import json
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy.pool import NullPool
import hashlib

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.database.models import (
    Base, Department, Teacher, Secretary, TemplateForm, TemplateFormField,
    CollectTask, CollectTaskTarget, SentAttachment, SentEmail,
    ReceivedAttachment, ReceivedEmail, Aggregation,
    DataType, EmailStatus, TaskStatus
)
from backend.database.db_config import get_engine, get_session_factory
from backend.storage_service import ensure_minio_running
from backend.storage_service.storage import parse_path
from backend.utils import ensure_utc


def hash_password(password: str) -> str:
    """
    Simple password hashing (use bcrypt in production)
    
    Args:
        password: Plain text password
    
    Returns:
        Hashed password
    """
    return hashlib.sha256(password.encode()).hexdigest()


def drop_all_tables(engine):
    """
    Drop all tables in the database that belong to this project
    
    Args:
        engine: SQLAlchemy engine
    """
    print("Dropping all existing tables...")
    Base.metadata.drop_all(engine)
    print("✓ All tables dropped successfully")


def create_all_tables(engine):
    """
    Create all tables defined in models
    
    Args:
        engine: SQLAlchemy engine
    """
    print("\nCreating all tables...")
    Base.metadata.create_all(engine)
    print("✓ All tables created successfully")


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
    
    print("✓ JSON structure validation passed")


def load_default_data(session, data_file: str):
    """
    Load default data from JSON file into database
    
    Args:
        session: SQLAlchemy session
        data_file: Path to JSON file
    """
    print(f"\nLoading default data from {data_file}...")
    
    # Read JSON file
    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Validate JSON structure (ensure no old table/field names)
    validate_json_structure(data)
    
    # Department ID mapping
    dept_id_map = {}
    
    # 1. Load Departments
    if 'departments' in data:
        print("  Loading departments...")
        for dept_data in data['departments']:
            dept = Department(
                name=dept_data['name'],
            )
            session.add(dept)
            session.flush()  # Get the ID
            dept_id_map[dept_data['name']] = dept.id
        session.commit()
        print(f"    ✓ Loaded {len(data['departments'])} departments")
    
    # 2. Load Teachers
    teacher_id_map = {}
    if 'teachers' in data:
        print("  Loading teachers...")
        for teacher_data in data['teachers']:
            dept_name = teacher_data.get('department_name')
            dept_id = dept_id_map.get(dept_name)
            
            if dept_id is None:
                print(f"    Warning: Department '{dept_name}' not found for teacher {teacher_data['name']}")
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
        print(f"    ✓ Loaded {len(data['teachers'])} teachers")
    
    # 3. Load Secretaries
    secretary_id_map = {}
    if 'secretaries' in data:
        print("  Loading secretaries...")
        for sec_data in data['secretaries']:
            dept_name = sec_data.get('department_name')
            dept_id = dept_id_map.get(dept_name)
            
            if dept_id is None:
                print(f"    Warning: Department '{dept_name}' not found for secretary {sec_data['name']}")
                continue
            
            secretary = Secretary(
                id=sec_data['id'],  # 工号，手动指定
                name=sec_data['name'],
                department_id=dept_id,
                username=sec_data['username'],
                account=sec_data['account'],
                password_hash=hash_password(sec_data.get('password', '123456')),
                email=sec_data['email'],
                phone=sec_data.get('phone'),
            )
            session.add(secretary)
            session.flush()
            secretary_id_map[secretary.id] = secretary.id
        session.commit()
        print(f"    ✓ Loaded {len(data['secretaries'])} secretaries")
    
    # 4. Load Template Forms
    template_id_map = {}
    if 'template_forms' in data:
        print("  Loading template forms...")
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
        print(f"    ✓ Loaded {len(data['template_forms'])} template forms")
    
    # 5. Load Template Form Fields
    if 'template_form_fields' in data:
        print("  Loading template form fields...")
        for field_data in data['template_form_fields']:
            # Get form_id from form_index
            form_index = field_data.get('form_index', 0)
            if form_index not in template_id_map:
                print(f"    ⚠ Warning: form_index {form_index} not found, skipping field")
                continue
            
            form_id = template_id_map[form_index]
            
            # Convert data_type string to enum
            from backend.database.models import DataType
            data_type_str = field_data.get('data_type', 'TEXT')
            data_type = DataType[data_type_str] if hasattr(DataType, data_type_str) else DataType.TEXT
            
            field = TemplateFormField(
                form_id=form_id,
                ord=field_data.get('ord', 0),
                display_name=field_data['display_name'],
                data_type=data_type,
                required=field_data.get('required', False),
            )
            session.add(field)
        session.commit()
        print(f"    ✓ Loaded {len(data['template_form_fields'])} template fields")
    
    # 6. Load Collect Tasks
    task_id_map = {}
    if 'collect_tasks' in data:
        print("  Loading collect tasks...")
        for idx, task_data in enumerate(data['collect_tasks']):
            # Get template_id from first template
            if 0 not in template_id_map:
                print("    ⚠ Warning: No template form created yet, skipping tasks")
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
                        print(f"    ⚠ Warning: teacher_id {teacher_id} not found, skipping target")
                        continue
                    
                    target = CollectTaskTarget(
                        task_id=task.id,
                        teacher_id=teacher_id
                    )
                    session.add(target)
        
        session.commit()
        print(f"    ✓ Loaded {len(data['collect_tasks'])} collect tasks")
    
    # 7. Load Sent Attachments
    sent_attach_id_map = {}
    if 'sent_attachments' in data:
        print("  Loading sent attachments...")
        
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
                        print(f"    ✓ Uploaded: {file_name} -> {file_path}")
                    except Exception as e:
                        error_msg = f"Failed to upload {file_name}: {e}"
                        print(f"    ❌ {error_msg}")
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
        print(f"    ✓ Loaded {len(data['sent_attachments'])} sent attachments")
    
    # 9. Load Sent Emails
    if 'sent_emails' in data:
        print("  Loading sent emails...")
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
        print(f"    ✓ Loaded {len(data['sent_emails'])} sent emails")
    
    # 10. Load Received Attachments
    recv_attach_id_map = {}
    if 'received_attachments' in data:
        print("  Loading received attachments...")
        
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
                        print(f"    ✓ Uploaded: {file_name} -> {file_path}")
                    except Exception as e:
                        error_msg = f"Failed to upload {file_name}: {e}"
                        print(f"    ❌ {error_msg}")
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
        print(f"    ✓ Loaded {len(data['received_attachments'])} received attachments")
    
    # 11. Load Received Emails
    if 'received_emails' in data:
        print("  Loading received emails...")
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
        print(f"    ✓ Loaded {len(data['received_emails'])} received emails")
    
    print("\n✓ All default data loaded successfully")


def reset_database(data_file: str = None):
    """
    Complete database reset: drop, create, and load data
    Also initializes MinIO and uploads default attachments
    
    Args:
        data_file: Path to default data JSON file. If None, uses default location.
    """
    if data_file is None:
        data_file = str(Path(__file__).parent / "default_data" / "default_data.json")

    # Step 1: Ensure MinIO is running and bucket exists
    print("\n[1/4] Starting MinIO service...")
    bucket_is_new = False
    try:
        ensure_minio_running()
        print("✓ MinIO service is running")
        
        # Ensure bucket exists
        from backend.storage_service.minio_service import ensure_bucket_exists
        bucket_is_new = ensure_bucket_exists()
    except Exception as e:
        error_msg = f"MinIO initialization failed: {e}"
        print(f"❌ {error_msg}")
        raise RuntimeError(error_msg) from e
    
    # Step 2: Clear MinIO bucket (only if it already existed)
    if not bucket_is_new:
        print("\n[2/4] Clearing existing MinIO bucket...")
        try:
            from backend.storage_service.minio_service import get_minio_client
            from minio.deleteobjects import DeleteObject
            
            client = get_minio_client()
            bucket = os.getenv('MINIO_BUCKET', 'mailmerge')
            
            # List all objects
            objects = client.list_objects(bucket_name=bucket, recursive=True)
            object_names = [obj.object_name for obj in objects]
            
            if not object_names:
                print(f"Bucket '{bucket}' is already empty.")
            else:
                # Delete all objects
                delete_object_list = [DeleteObject(name) for name in object_names]
                errors = client.remove_objects(bucket_name=bucket, delete_object_list=delete_object_list)
                
                # Check for errors
                error_count = 0
                for error in errors:
                    print(f"Error deleting {error.object_name}: {error}")
                    error_count += 1
                
                deleted_count = len(object_names) - error_count
                print(f"✓ Cleared {deleted_count} objects from MinIO bucket '{bucket}'")
        except Exception as e:
            error_msg = f"Failed to clear MinIO bucket: {e}"
            print(f"❌ {error_msg}")
            raise RuntimeError(error_msg) from e
    else:
        print("\n[2/4] Skipping bucket clear (bucket was just created)")
    
    # Step 3: Ensure database exists
    print("\n[3/4] Ensuring database exists...")
    from backend.database.db_config import ensure_database_exists
    db_is_new = ensure_database_exists()
    
    # Step 4: Reset database tables (drop and recreate)
    print("\n[4/4] Resetting database tables...")
    # Use NullPool to avoid connection pool issues in scripts
    engine = get_engine(echo=False, poolclass=NullPool)
    
    # Drop and create tables (skip drop if database was just created)
    if not db_is_new:
        drop_all_tables(engine)
    else:
        print("Skipping table drop (database was just created)")
    
    create_all_tables(engine)

    
    
if __name__ == "__main__":
    reset_database()