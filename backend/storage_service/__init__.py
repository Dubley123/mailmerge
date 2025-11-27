"""
Storage Service Package
Provides unified storage interface for both MinIO and local filesystem
"""
from backend.storage_service.minio_service import ensure_minio_running, get_minio_client
from backend.storage_service.storage import upload, download

__all__ = [
    'ensure_minio_running',
    'get_minio_client',
    'upload',
    'download'
]
