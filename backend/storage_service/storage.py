"""
Storage Module
Provides unified upload/download interface for both MinIO and local filesystem
"""
import os
from typing import Dict, Literal
from urllib.parse import urlparse
from dotenv import load_dotenv
from minio.error import S3Error

load_dotenv()

MINIO_BUCKET = os.getenv('MINIO_BUCKET', 'mailmerge')
LOCAL_DATA_ROOT = os.getenv('LOCAL_DATA_ROOT', '')


def parse_path(path: str) -> Dict:
    """
    Parse a storage path and return storage type and location details.
    
    解析优先级:
    1. 如果有前缀(local://或minio://)，直接判断类型
    2. 如果是没有前缀的相对路径，尝试解析为MinIO路径
    3. 如果是绝对路径，解析为本地文件系统路径
    
    Args:
        path: Storage path (with or without prefix)
        
    Returns:
        Dict with keys:
        - type: 'local' or 'minio'
        - For local: 'abs_path' (absolute path)
        - For minio: 'bucket', 'object_name'
        
    Raises:
        ValueError: If path format is invalid
    """
    if not path or not path.strip():
        raise ValueError("Path cannot be empty")
    
    path = path.strip()
    
    # Case 1: Explicit local:// prefix
    if path.startswith('local://'):
        local_path = path[len('local://'):]
        
        # If absolute path
        if os.path.isabs(local_path):
            return {
                'type': 'local',
                'abs_path': local_path
            }
        
        # If relative path, resolve against LOCAL_DATA_ROOT
        if not LOCAL_DATA_ROOT:
            raise ValueError(f"LOCAL_DATA_ROOT not configured for relative path: {local_path}")
        
        abs_path = os.path.join(LOCAL_DATA_ROOT, local_path)
        return {
            'type': 'local',
            'abs_path': abs_path
        }
    
    # Case 2: Explicit minio:// or s3:// prefix
    if path.startswith('minio://') or path.startswith('s3://'):
        parsed = urlparse(path)
        bucket = parsed.netloc or MINIO_BUCKET
        object_name = parsed.path.lstrip('/')
        
        if not object_name:
            raise ValueError(f"Invalid MinIO path (missing object name): {path}")
        
        return {
            'type': 'minio',
            'bucket': bucket,
            'object_name': object_name
        }
    
    # Case 3: Absolute path (local filesystem)
    if os.path.isabs(path):
        return {
            'type': 'local',
            'abs_path': path
        }
    
    # Case 4: Relative path without prefix
    # Try MinIO first: assume format like "attachment/1/file.xlsx" or "bucket/attachment/1/file.xlsx"
    parts = path.split('/', 1)
    
    # Check if first part might be a bucket name
    if len(parts) == 2:
        # Could be "bucket/object" or just "folder/file"
        # Assume MinIO format with default bucket
        return {
            'type': 'minio',
            'bucket': MINIO_BUCKET,
            'object_name': path
        }
    
    # Single part or no clear structure - try MinIO
    if len(parts) == 1:
        return {
            'type': 'minio',
            'bucket': MINIO_BUCKET,
            'object_name': path
        }
    
    raise ValueError(f"Unable to parse path: {path}")


def upload(local_file_path: str, target_path: str) -> str:
    """
    Upload a file from local filesystem to target storage location.
    
    Args:
        local_file_path: Local filesystem path (no prefix needed)
        target_path: Target storage path (must have local:// or minio:// prefix)
        
    Returns:
        Final storage path with prefix (local:// or minio://)
        
    Raises:
        FileNotFoundError: If local_file_path doesn't exist
        ValueError: If target_path format is invalid
        RuntimeError: If upload fails
    """
    # Validate source file exists
    if not os.path.exists(local_file_path):
        raise FileNotFoundError(f"Source file not found: {local_file_path}")
    
    # Parse target path
    parsed = parse_path(target_path)
    
    if parsed['type'] == 'local':
        # Local storage
        target_abs_path = parsed['abs_path']
        
        # Create parent directory if needed
        os.makedirs(os.path.dirname(target_abs_path), exist_ok=True)
        
        # Copy file
        import shutil
        shutil.copy2(local_file_path, target_abs_path)
        
        return f"local://{target_abs_path}"
    
    elif parsed['type'] == 'minio':
        # MinIO storage
        bucket = parsed['bucket']
        object_name = parsed['object_name']
        
        try:
            from backend.storage_service.minio_service import get_minio_client
            client = get_minio_client()
            
            # Ensure bucket exists
            if not client.bucket_exists(bucket_name=bucket):
                client.make_bucket(bucket_name=bucket)
            
            # Upload file
            client.fput_object(
                bucket_name=bucket,
                object_name=object_name,
                file_path=local_file_path
            )
            
            return f"minio://{bucket}/{object_name}"
            
        except S3Error as e:
            raise RuntimeError(f"MinIO upload failed: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Upload failed: {str(e)}")
    
    else:
        raise ValueError(f"Unknown storage type: {parsed['type']}")


def download(source_path: str, local_file_path: str) -> str:
    """
    Download a file from storage to local filesystem.
    
    Args:
        source_path: Source storage path (must have local:// or minio:// prefix)
        local_file_path: Local filesystem path to save (no prefix needed)
        
    Returns:
        Absolute path of downloaded file
        
    Raises:
        FileNotFoundError: If source file doesn't exist
        ValueError: If source_path format is invalid
        RuntimeError: If download fails
    """
    # Parse source path
    parsed = parse_path(source_path)
    
    if parsed['type'] == 'local':
        # Local storage - just copy
        source_abs_path = parsed['abs_path']
        
        if not os.path.exists(source_abs_path):
            raise FileNotFoundError(f"Source file not found: {source_abs_path}")
        
        # Create parent directory for destination
        os.makedirs(os.path.dirname(os.path.abspath(local_file_path)), exist_ok=True)
        
        # Copy file
        import shutil
        shutil.copy2(source_abs_path, local_file_path)
        
        return os.path.abspath(local_file_path)
    
    elif parsed['type'] == 'minio':
        # MinIO storage
        bucket = parsed['bucket']
        object_name = parsed['object_name']
        
        try:
            from backend.storage_service.minio_service import get_minio_client
            client = get_minio_client()
            
            # Create parent directory for destination
            os.makedirs(os.path.dirname(os.path.abspath(local_file_path)), exist_ok=True)
            
            # Download file
            client.fget_object(
                bucket_name=bucket,
                object_name=object_name,
                file_path=local_file_path
            )
            
            return os.path.abspath(local_file_path)
            
        except S3Error as e:
            raise RuntimeError(f"MinIO download failed: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Download failed: {str(e)}")
    
    else:
        raise ValueError(f"Unknown storage type: {parsed['type']}")


def delete(target_path: str) -> bool:
    """
    Delete a file from storage.
    
    Args:
        target_path: Target storage path (must have local:// or minio:// prefix)
        
    Returns:
        bool: True if deletion was successful (or file didn't exist), False otherwise
        
    Raises:
        ValueError: If target_path format is invalid
        RuntimeError: If deletion fails
    """
    # Parse target path
    parsed = parse_path(target_path)
    
    if parsed['type'] == 'local':
        # Local storage
        target_abs_path = parsed['abs_path']
        
        if os.path.exists(target_abs_path):
            try:
                os.remove(target_abs_path)
                return True
            except Exception as e:
                raise RuntimeError(f"Failed to delete local file: {str(e)}")
        return True
    
    elif parsed['type'] == 'minio':
        # MinIO storage
        bucket = parsed['bucket']
        object_name = parsed['object_name']
        
        try:
            from backend.storage_service.minio_service import get_minio_client
            client = get_minio_client()
            
            # Delete object
            client.remove_object(bucket_name=bucket, object_name=object_name)
            return True
            
        except S3Error as e:
            raise RuntimeError(f"MinIO deletion failed: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Deletion failed: {str(e)}")
    
    else:
        raise ValueError(f"Unknown storage type: {parsed['type']}")
