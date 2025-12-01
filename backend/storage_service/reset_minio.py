"""
MinIO Reset Script
Clears all objects from the configured MinIO bucket
"""
import os
from backend.logger import get_logger
from backend.storage_service.minio_service import get_minio_client
from minio.deleteobjects import DeleteObject

logger = get_logger(__name__)

def reset_minio():
    """
    Clear all objects from the MinIO bucket
    """
    logger.info("Clearing existing MinIO bucket...")
    try:
        client = get_minio_client()
        bucket = os.getenv('MINIO_BUCKET', 'mailmerge')
        
        # Check if bucket exists first
        if client.bucket_exists(bucket_name=bucket):
            # List all objects
            objects = client.list_objects(bucket_name=bucket, recursive=True)
            object_names = [obj.object_name for obj in objects]
            
            if not object_names:
                logger.info(f"Bucket '{bucket}' is already empty.")
            else:
                # Delete all objects
                delete_object_list = [DeleteObject(name) for name in object_names]
                errors = client.remove_objects(bucket_name=bucket, delete_object_list=delete_object_list)
                
                # Check for errors
                error_count = 0
                for error in errors:
                    logger.error(f"Error deleting {error.object_name}: {error}")
                    error_count += 1
                
                deleted_count = len(object_names) - error_count
                logger.info(f"Cleared {deleted_count} objects from MinIO bucket '{bucket}'")
        else:
             logger.warning(f"Bucket '{bucket}' does not exist, skipping clear.")

    except Exception as e:
        error_msg = f"Failed to clear MinIO bucket: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e

if __name__ == "__main__":
    reset_minio()
