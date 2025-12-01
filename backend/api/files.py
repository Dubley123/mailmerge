from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import os
import tempfile

from backend.database.db_config import get_db_session
from backend.api.auth import get_current_user
from backend.database.models import SentAttachment, ReceivedAttachment, Secretary
from backend.storage_service import download
from backend.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()

@router.get("/sent/{attachment_id}")
def download_sent_attachment(
    attachment_id: int,
    db: Session = Depends(get_db_session),
    current_user: Secretary = Depends(get_current_user)
):
    """Download a sent attachment"""
    logger.info(f"Downloading sent attachment {attachment_id} for user {current_user.id}")
    attachment = db.query(SentAttachment).filter(SentAttachment.id == attachment_id).first()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    
    try:
        source_path = attachment.file_path
        original_filename = attachment.file_name or os.path.basename(source_path)
        
        # Create temp file path
        temp_dir = tempfile.gettempdir()
        # Use a unique name to avoid conflicts
        local_file_path = os.path.join(temp_dir, f"sent_{attachment_id}_{original_filename}")
        
        # Download using storage service
        downloaded_path = download(source_path, local_file_path)
        
        return FileResponse(
            path=downloaded_path,
            filename=original_filename,
            media_type=attachment.content_type or "application/octet-stream"
        )
    except Exception as e:
        logger.error(f"Download error: {e}")
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


@router.get("/received/{attachment_id}")
def download_received_attachment(
    attachment_id: int,
    db: Session = Depends(get_db_session),
    current_user: Secretary = Depends(get_current_user)
):
    """Download a received attachment"""
    logger.info(f"Downloading received attachment {attachment_id} for user {current_user.id}")
    attachment = db.query(ReceivedAttachment).filter(ReceivedAttachment.id == attachment_id).first()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    
    try:
        source_path = attachment.file_path
        original_filename = attachment.file_name or os.path.basename(source_path)
        
        # Create temp file path
        temp_dir = tempfile.gettempdir()
        local_file_path = os.path.join(temp_dir, f"recv_{attachment_id}_{original_filename}")
        
        # Download using storage service
        downloaded_path = download(source_path, local_file_path)
        
        return FileResponse(
            path=downloaded_path,
            filename=original_filename,
            media_type=attachment.content_type or "application/octet-stream"
        )
    except Exception as e:
        logger.error(f"Download error: {e}")
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")
