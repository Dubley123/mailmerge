"""
Database Reset Script
Drops and recreates all tables, then loads default data
Clears and re-uploads MinIO attachments
"""
import sys
import os
from pathlib import Path
from sqlalchemy.pool import NullPool

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.database.models import Base
from backend.storage_service import ensure_minio_running
from backend.database.db_config import get_engine


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