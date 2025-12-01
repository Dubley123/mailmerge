"""
MinIO Service Module
Provides MinIO client initialization and service management
"""
import subprocess
import os
from minio import Minio
from dotenv import load_dotenv
from backend.logger import get_logger

logger = get_logger(__name__)

load_dotenv()

MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT')
MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY')
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY')
MINIO_SECURE = os.getenv('MINIO_SECURE', 'false').lower() in ('1', 'true', 'yes')

_minio_client = None


def ensure_minio_running():
    """
    Start MinIO service using docker-compose or docker compose.
    Checks if container is already running before starting.
    """
    compose_file = os.path.join(os.path.dirname(__file__), 'docker-compose.yml')
    container_name = "mailmerge_minio"
    
    logger.info("Checking MinIO service...")
    
    # Check if container is already running
    try:
        result = subprocess.run(
            ["docker", "ps", "-q", "-f", f"name={container_name}"],
            capture_output=True,
            text=True,
            check=True
        )
        if result.stdout.strip():
            logger.info(f"MinIO container '{container_name}' is already running.")
            return
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        logger.warning(f"Unable to check Docker status: {e}")
    
    # Determine which command to use
    compose_cmd = None
    
    # Try docker compose (v2) first as it is the modern standard
    try:
        subprocess.run(["docker", "compose", "version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        compose_cmd = ["docker", "compose"]
    except (FileNotFoundError, subprocess.CalledProcessError):
        # Try legacy docker-compose
        try:
            subprocess.run(["docker-compose", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            compose_cmd = ["docker-compose"]
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass
            
    if not compose_cmd:
        error_msg = "Docker Compose not found (neither 'docker compose' nor 'docker-compose'). MinIO service cannot be started."
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    try:
        # Start MinIO (this will restart if container exists but is stopped)
        logger.info("Starting MinIO service...")
        cmd = compose_cmd + ["-f", compose_file, "up", "-d"]
        subprocess.run(cmd, check=True, capture_output=True)
        logger.info("MinIO service started.")
        
    except subprocess.CalledProcessError as e:
        # If failed due to container name conflict, try to remove and restart
        if "already in use" in str(e.stderr):
            logger.warning(f"Container name conflict detected. Removing old container...")
            try:
                subprocess.run(["docker", "rm", "-f", container_name], check=True, capture_output=True)
                subprocess.run(cmd, check=True, capture_output=True)
                logger.info("MinIO service started after cleanup.")
            except subprocess.CalledProcessError as e2:
                error_msg = f"Failed to restart MinIO after cleanup: {e2}"
                logger.error(error_msg)
                raise RuntimeError(error_msg) from e2
        else:
            error_msg = f"Failed to start MinIO: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e


def get_minio_client():
    """
    Get or create MinIO client instance.
    
    Returns:
        Minio: MinIO client instance
        
    Raises:
        RuntimeError: If MinIO configuration is missing
    """
    global _minio_client
    if _minio_client is None:
        if not MINIO_ENDPOINT or not MINIO_ACCESS_KEY or not MINIO_SECRET_KEY:
            raise RuntimeError('MinIO configuration missing in environment variables')
        
        _minio_client = Minio(
            endpoint=MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE
        )
    return _minio_client


def ensure_bucket_exists():
    """
    Ensure the MinIO bucket exists, create it if it doesn't.
    
    Returns:
        bool: True if bucket was newly created, False if it already existed
    """
    try:
        client = get_minio_client()
        bucket = os.getenv('MINIO_BUCKET', 'mailmerge')
        
        if client.bucket_exists(bucket_name=bucket):
            logger.info(f"MinIO bucket '{bucket}' already exists")
            return False  # Bucket already exists
        else:
            logger.info(f"MinIO bucket '{bucket}' does not exist, creating...")
            client.make_bucket(bucket_name=bucket)
            logger.info(f"MinIO bucket '{bucket}' created successfully")
            return True  # Bucket was newly created
    except Exception as e:
        logger.error(f"Failed to ensure bucket exists: {e}")
        raise
