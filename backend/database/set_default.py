"""
set_default.py

Load default data (generate/insert) into the database and upload attachments to MinIO.
This is intentionally separated from the reset script so `--reset` only clears,
and `--set-default` will populate default data.
"""
import sys
import os
from pathlib import Path
from sqlalchemy.pool import NullPool

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.database.reset_db import load_default_data
from backend.database.db_config import get_engine, get_session_factory
from backend.storage_service import ensure_minio_running


def set_default(data_file: str = None):
    if data_file is None:
        data_file = str(Path(__file__).parent / "default_data" / "default_data.json")

    # Ensure MinIO running (attachments upload depends on storage)
    try:
        ensure_minio_running()
        print("✓ MinIO ensured")
    except Exception as e:
        print(f"⚠ Warning: MinIO initialization failed: {e}")
        print("  Default data load may fail if attachments need uploading.")

    # Create engine and session
    engine = get_engine(echo=False, poolclass=NullPool)
    SessionLocal = get_session_factory(engine)
    session = SessionLocal()

    if data_file and os.path.exists(data_file):
        try:
            load_default_data(session, data_file)
            print("\n✓ Default data inserted successfully.")
        except Exception as e:
            print(f"\n✗ Error loading default data: {e}")
            session.rollback()
            raise
        finally:
            session.close()
    else:
        print(f"No default data file found at: {data_file}")


if __name__ == '__main__':
    # Simple CLI: python set_default.py [path_to_json]
    data_file = sys.argv[1] if len(sys.argv) > 1 else None
    set_default(data_file)
