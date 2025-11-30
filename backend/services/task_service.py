"""
Task Service
Encapsulates business logic for task management, including aggregation and status updates.
"""
import os
import tempfile
import pandas as pd
import re
from datetime import datetime
from sqlalchemy.orm import Session
from backend.database.models import (
    CollectTask, TemplateForm, TemplateFormField, 
    ReceivedEmail, ReceivedAttachment, Aggregation, TaskStatus
)
from backend.storage_service import storage
from backend.utils import get_utc_now
from backend.services.email_publisher import publish_task_emails

def perform_aggregation(db: Session, task: CollectTask, user_id: int) -> dict:
    """
    Execute task aggregation logic.
    Collects all Excel attachments from received emails for a task and merges them into a single Excel file.
    """
    # Get template fields (ordered by ord)
    template = db.query(TemplateForm).filter(TemplateForm.id == task.template_id).first()
    if not template:
        raise Exception("Task template not found")

    template_fields = db.query(TemplateFormField).filter(
        TemplateFormField.form_id == template.id
    ).order_by(TemplateFormField.ord).all()
    template_headers = [f.display_name for f in template_fields]
    # Map header -> validation rule JSON (None if not set)
    header_validation_map = {f.display_name: f.validation_rule for f in template_fields}

    # Collect received emails with attachments
    received_emails = db.query(ReceivedEmail).filter(
        ReceivedEmail.task_id == task.id,
        ReceivedEmail.attachment_id != None
    ).all()

    # if not received_emails:
    #     raise Exception("No replies with attachments received for this task")

    temp_files = []
    rows = []
    warnings = []
    processed_received_ids = []
    validation_issue_map = {}  # teacher_id -> list of {field, reason}

    try:
        for r in received_emails:
            if not r.attachment_id:
                continue
            att = db.query(ReceivedAttachment).filter(ReceivedAttachment.id == r.attachment_id).first()
            if not att:
                warnings.append(f"Attachment record not found (id={r.attachment_id})")
                continue

            file_path = att.file_path
            file_name = att.file_name or os.path.basename(file_path or '')
            if not file_path:
                warnings.append(f"Attachment path is empty (id={att.id})")
                continue

            # Check if Excel
            lower = (file_name or file_path).lower()
            if not (lower.endswith('.xlsx') or lower.endswith('.xls')):
                warnings.append(f"Ignoring non-Excel attachment: {file_name}")
                continue

            # Download attachment to local temp file
            try:
                tmp_fd, local_tmp = tempfile.mkstemp(suffix=os.path.splitext(file_name)[1])
                os.close(tmp_fd)
                temp_files.append(local_tmp)
                
                storage.download(file_path, local_tmp)
            except Exception as e:
                warnings.append(f"Failed to download attachment (id={att.id}): {e}")
                continue

            # Read Excel
            try:
                df = pd.read_excel(local_tmp, engine='openpyxl')
            except Exception as e:
                warnings.append(f"Failed to parse Excel (id={att.id}): {e}")
                continue

            if df.shape[0] == 0:
                warnings.append(f"Attachment has no data (id={att.id}): {file_name}")
                continue

            if df.shape[0] > 1:
                warnings.append(f"Attachment contains more than one row (id={att.id}), taking only the first row: {file_name}")

            # Take first row and filter/reorder by template fields
            first_row = df.iloc[0]
            col_map = {str(col).strip(): col for col in df.columns}

            row_values = []
            for header in template_headers:
                key = header.strip()
                if key in col_map:
                    val = first_row[col_map[key]]
                    try:
                        if pd.isna(val):
                            val = None
                    except Exception:
                        pass
                    row_values.append(val)
                else:
                    row_values.append(None)
                # Validation: if validation_rule exists, validate the value
                rule = header_validation_map.get(header)
                if rule:
                    ok, reason = _validate_value(val, rule)
                    if not ok:
                        # use teacher id if available, otherwise received email id
                        teacher_id = getattr(r, 'from_tea_id', None)
                        key_id = str(teacher_id) if teacher_id else f"rec_{r.id}"
                        validation_issue_map.setdefault(key_id, []).append({
                            'field': header,
                            'reason': reason,
                            'value': None if pd.isna(val) else str(val)
                        })

            rows.append(row_values)
            processed_received_ids.append(r.id)

        if len(rows) == 0:
            # raise Exception(f"No mergeable Excel attachments found. Details: {warnings}")
            print(f"Warning: No mergeable Excel attachments found. Details: {warnings}")

        # Build DataFrame
        out_df = pd.DataFrame(rows, columns=template_headers)

        # Save to local temp file
        tmp_out_fd, tmp_out_path = tempfile.mkstemp(suffix='.xlsx')
        os.close(tmp_out_fd)
        temp_files.append(tmp_out_path)
        
        try:
            out_df.to_excel(tmp_out_path, index=False)
        except Exception as e:
            raise Exception(f"Failed to generate aggregated Excel: {e}")

        # Check if aggregation record exists
        existing_agg = db.query(Aggregation).filter(Aggregation.task_id == task.id).first()
        
        # Use task name as filename, preserve Chinese, remove timestamp suffix
        safe_task_name = "".join(c for c in task.name if c not in r'<>:"/\|?*')
        filename = f"{safe_task_name}_汇总表.xlsx"
        
        if existing_agg:
            # Delete old file
            if existing_agg.file_path:
                try:
                    storage.delete(existing_agg.file_path)
                except Exception as e:
                    print(f"Warning: Failed to delete old aggregation file: {e}")

            # Update existing record
            agg = existing_agg
            agg.generated_by = user_id
            agg.generated_at = get_utc_now()
            agg.record_count = len(out_df)
            agg.has_validation_issues = True if validation_issue_map else False
            agg.validation_errors = validation_issue_map if validation_issue_map else None
        else:
            # Create new record
            agg = Aggregation(
                task_id=task.id,
                name=f"{task.name}_汇总表",
                generated_by=user_id,
                record_count=len(out_df),
                file_path="",
                has_validation_issues=True if validation_issue_map else False,
                validation_errors=validation_issue_map if validation_issue_map else None
            )
            db.add(agg)
        
        db.flush() # Get ID

        # Save file
        target_path = f"minio://mailmerge/aggregation/{agg.id}/{filename}"
        try:
            uploaded_path = storage.upload(tmp_out_path, target_path)
        except Exception as e:
            raise Exception(f"Failed to save aggregated file: {e}")

        # Update Aggregation.file_path
        agg.file_path = uploaded_path
        
        # Mark processed ReceivedEmails as aggregated
        if processed_received_ids:
            db.query(ReceivedEmail).filter(ReceivedEmail.id.in_(processed_received_ids)).update({"is_aggregated": True}, synchronize_session=False)
        
        return {
            "aggregation_id": agg.id,
            "file_path": uploaded_path,
            "warnings": warnings
        }

    finally:
        for f in temp_files:
            try:
                if f and os.path.exists(f):
                    os.remove(f)
            except Exception:
                pass


def _validate_value(value, rule: dict):
        """
        Validate a single value against a rule dict.
        Returns: (True, None) if passed; (False, reason) if failed
        """
        # Normalize
        if rule is None:
            return True, None

        required = bool(rule.get('required', False))
        vtype = (rule.get('type') or '').upper() if rule.get('type') else None

        # None/empty checks
        if value is None or (isinstance(value, str) and value.strip() == ''):
            if required:
                return False, 'Required field is empty'
            return True, None

        # Strings: strip
        if isinstance(value, str):
            vstr = value.strip()
        else:
            vstr = None

        # TYPE checks
        try:
            if vtype in (None, 'TEXT'):
                # length checks
                if vstr is not None:
                    if 'min_length' in rule and len(vstr) < int(rule['min_length']):
                        return False, f"Length smaller than {rule['min_length']}"
                    if 'max_length' in rule and len(vstr) > int(rule['max_length']):
                        return False, f"Length greater than {rule['max_length']}"
                return True, None

            if vtype == 'INTEGER':
                try:
                    if isinstance(value, float) and not float(value).is_integer():
                        return False, 'Not an integer'
                    int(value)
                except Exception:
                    return False, 'Not a valid integer'
                return True, None

            if vtype == 'FLOAT':
                try:
                    float(value)
                except Exception:
                    return False, 'Not a valid float/number'
                return True, None

            if vtype == 'NUMBER':
                # Legacy: accept integer or float
                try:
                    num = float(value)
                except Exception:
                    return False, 'Not a valid number'
                if 'min' in rule and num < float(rule['min']):
                    return False, f"Below minimum {rule['min']}"
                if 'max' in rule and num > float(rule['max']):
                    return False, f"Above maximum {rule['max']}"
                return True, None

            if vtype in ('DATE', 'DATETIME'):
                try:
                    # Use pandas to parse
                    import pandas as _pd
                    dt = _pd.to_datetime(value, errors='coerce')
                    if pd.isna(dt):
                        return False, 'Not a valid date/datetime'
                except Exception:
                    return False, 'Not a valid date/datetime'
                return True, None

            if vtype == 'BOOLEAN':
                if isinstance(value, bool):
                    return True, None
                if isinstance(value, (int, float)):
                    return True, None
                if isinstance(value, str):
                    if vstr.lower() in ['true', 'false', 'yes', 'no', '是', '否', '1', '0']:
                        return True, None
                return False, 'Not a valid boolean value'

            if vtype == 'EMAIL':
                email_re = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
                if isinstance(value, str) and email_re.match(value.strip()):
                    return True, None
                return False, 'Not a valid email address'

            if vtype == 'PHONE':
                # Chinese mobile basic validation
                phone_re = re.compile(r"^1[3-9]\d{9}$")
                if isinstance(value, str) and phone_re.match(value.strip()):
                    return True, None
                return False, 'Not a valid phone number'

            if vtype == 'ID_CARD':
                # Chinese ID: 15 or 18 characters (last digit can be X/x)
                if isinstance(value, (int, float)):
                    s = str(int(value))
                else:
                    s = str(value).strip()
                if re.fullmatch(r"\d{15}|\d{17}[\dXx]", s):
                    return True, None
                return False, 'Not a valid ID card number'

            if vtype == 'EMPLOYEE_ID' or vtype == 'ID' or vtype == 'EMP_ID':
                # allow 5-20 chars alnum
                if isinstance(value, (int, float)):
                    s = str(int(value))
                else:
                    s = str(value).strip()
                if re.fullmatch(r"\d{10}", s):
                    return True, None
                return False, 'Not a valid employee/id value'

            # Options constraint (if present) - regardless of type
            if 'options' in rule and rule.get('options'):
                opts = rule.get('options') or []
                if isinstance(value, str) and ',' in value:
                    vals = [v.strip() for v in str(value).split(',') if v.strip()]
                    for vv in vals:
                        if opts and vv not in opts:
                            return False, f"Value '{vv}' not in allowed options"
                else:
                    if opts and str(value).strip() not in opts:
                        return False, f"Value not in allowed options: {opts}"
                return True, None

            # regex check
            if 'regex' in rule:
                try:
                    rx = re.compile(rule['regex'])
                    if isinstance(value, str) and rx.match(value.strip()):
                        return True, None
                    return False, 'Regex mismatch'
                except Exception:
                    return False, 'Invalid regex in rule'

            # default allow
            return True, None
        except Exception as ex:
            return False, f'Validation error: {str(ex)}'


def check_task_status(task: CollectTask, db: Session):
    """
    Check and update task status based on time and events.
    """
    now = get_utc_now()
    
    # 1. DRAFT -> ACTIVE (Reached start time)
    if task.status == TaskStatus.DRAFT and task.started_time and task.started_time <= now:
        task.status = TaskStatus.ACTIVE
        db.add(task)
        db.commit()
        print(f"[Scheduler] Task {task.id} activated.")
        
        # Trigger email publishing
        try:
            print(f"[Scheduler] Publishing emails for task {task.id}...")
            publish_task_emails(db, task.id)
        except Exception as e:
            print(f"[Scheduler] Failed to publish emails for task {task.id}: {e}")
        
    # 2. ACTIVE -> CLOSED -> AGGREGATED (Reached deadline)
    if task.status == TaskStatus.ACTIVE and task.deadline and task.deadline <= now:
        # Auto close
        task.status = TaskStatus.CLOSED
        db.add(task)
        db.commit()
        print(f"[Scheduler] Task {task.id} closed (deadline reached).")
        
        # Auto aggregate
        try:
            # Check if there are emails
            # has_emails = db.query(ReceivedEmail).filter(
            #     ReceivedEmail.task_id == task.id,
            #     ReceivedEmail.attachment_id != None
            # ).count() > 0
            
            # if has_emails:
            perform_aggregation(db, task, task.created_by)
            task.status = TaskStatus.AGGREGATED
            db.add(task)
            db.commit()
            print(f"[Scheduler] Task {task.id} aggregated.")
        except Exception as e:
            print(f"[Scheduler] Auto aggregation failed for task {task.id}: {e}")
            # Keep CLOSED status
            
    # 3. AGGREGATED -> NEEDS_REAGGREGATION (New emails arrived)
    if task.status == TaskStatus.AGGREGATED:
        new_emails = db.query(ReceivedEmail).filter(
            ReceivedEmail.task_id == task.id,
            ReceivedEmail.is_aggregated == False
        ).count()
        
        if new_emails > 0:
            task.status = TaskStatus.NEEDS_REAGGREGATION
            db.add(task)
            db.commit()
            print(f"[Scheduler] Task {task.id} marked as NEEDS_REAGGREGATION.")
