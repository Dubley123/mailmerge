"""
Create Database Script
Creates the PostgreSQL database if it doesn't exist
"""
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "mailmerge")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")


def create_database():
    """Create database if it doesn't exist"""
    print(f"Creating database '{DB_NAME}' if not exists...")
    
    try:
        # Connect to PostgreSQL server (postgres database)
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database="postgres"  # Connect to default database
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Check if database exists
        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (DB_NAME,)
        )
        exists = cursor.fetchone()
        
        if exists:
            print(f"✓ Database '{DB_NAME}' already exists")
        else:
            # Create database
            cursor.execute(f'CREATE DATABASE {DB_NAME}')
            print(f"✓ Database '{DB_NAME}' created successfully")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"✗ Error creating database: {e}")
        return False


if __name__ == "__main__":
    import sys
    success = create_database()
    sys.exit(0 if success else 1)
