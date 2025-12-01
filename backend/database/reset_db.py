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
from backend.database.db_config import get_engine
from backend.logger import get_logger

logger = get_logger(__name__)

def drop_all_tables(engine):
    """
    Drop all tables in the database that belong to this project
    
    Args:
        engine: SQLAlchemy engine
    """
    logger.info("Dropping all existing tables...")
    Base.metadata.drop_all(engine)
    logger.info("All tables dropped successfully")


def create_all_tables(engine):
    """
    Create all tables defined in models
    
    Args:
        engine: SQLAlchemy engine
    """
    logger.info("Creating all tables...")
    Base.metadata.create_all(engine)
    logger.info("All tables created successfully")


def reset_database():
    """
    Complete database reset: drop and recreate all tables.
    """
    logger.info("Resetting database...")
    
    try:
        engine = get_engine(echo=False, poolclass=NullPool)
        
        logger.info("Dropping all database tables...")
        drop_all_tables(engine)
        logger.info("All database tables dropped.")
        
        logger.info("Recreating all database tables...")
        create_all_tables(engine)
        logger.info("All database tables recreated.")
        
        logger.info("Database reset successfully.")

    except Exception as e:
        error_msg = f"Failed to reset database: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e

    
if __name__ == "__main__":
    reset_database()
