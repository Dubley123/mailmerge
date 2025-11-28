"""
Task Service
Encapsulates business logic for task management, including aggregation and status updates.
"""
import os
import tempfile
import pandas as pd
from sqlalchemy.orm import Session
from backend.database.models import (
    CollectTask, TemplateForm, TemplateFormField, 
    ReceivedEmail, ReceivedAttachment, Aggregation, TaskStatus
)
from backend.storage_service import storage
from backend.utils import get_utc_now

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
        else:
            # Create new record
            agg = Aggregation(
                task_id=task.id,
                name=f"{task.name}_汇总表",
                generated_by=user_id,
                record_count=len(out_df),
                file_path=""
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
