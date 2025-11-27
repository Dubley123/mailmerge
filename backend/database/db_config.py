"""
Database Configuration Module
Handles database connection and session management
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration from environment
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "mailmerge")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# Construct database URL
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


def get_engine(echo=False, poolclass=None):
    """
    Create and return a SQLAlchemy engine
    
    Args:
        echo: If True, SQL statements will be logged
        poolclass: Connection pool class (use NullPool for scripts)
    
    Returns:
        SQLAlchemy Engine instance
    """
    return create_engine(
        DATABASE_URL,
        echo=echo,
        poolclass=poolclass,
        future=True
    )


def get_session_factory(engine=None):
    """
    Create and return a session factory
    
    Args:
        engine: SQLAlchemy engine (creates new one if None)
    
    Returns:
        SessionLocal class for creating sessions
    """
    if engine is None:
        engine = get_engine()
    
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine
    )
    return SessionLocal


def get_db_session():
    """
    Get a database session (for dependency injection in FastAPI)
    
    Yields:
        SQLAlchemy Session instance
    """
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_database_exists():
    """
    Ensure the database exists, create it if it doesn't.
    
    Returns:
        bool: True if database was newly created, False if it already existed
    """
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import OperationalError
    
    # First try to connect to the target database
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print(f"✓ Database '{DB_NAME}' already exists")
        return False  # Database already exists
    except OperationalError:
        # Database doesn't exist, create it
        print(f"Database '{DB_NAME}' does not exist, creating...")
        
        # Connect to default 'postgres' database to create our database
        default_url = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/postgres"
        default_engine = create_engine(default_url, isolation_level="AUTOCOMMIT")
        
        try:
            with default_engine.connect() as conn:
                conn.execute(text(f'CREATE DATABASE "{DB_NAME}"'))
            print(f"✓ Database '{DB_NAME}' created successfully")
            return True  # Database was newly created
        except Exception as e:
            print(f"❌ Failed to create database: {e}")
            raise
        finally:
            default_engine.dispose()


def test_connection():
    """
    Test database connection
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            from sqlalchemy import text
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        return True, "Database connection successful"
    except Exception as e:
        return False, f"Database connection failed: {str(e)}"


if __name__ == "__main__":
    # Test database connection when run directly
    success, message = test_connection()
    if success:
        print(f"✓ {message}")
        print(f"  Database: {DB_NAME}")
        print(f"  Host: {DB_HOST}:{DB_PORT}")
        print(f"  User: {DB_USER}")
    else:
        print(f"✗ {message}")
        exit(1)
