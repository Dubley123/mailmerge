"""
Background Scheduler
Handles periodic tasks such as checking task status and auto-aggregation.
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from backend.database.db_config import get_session_factory
from backend.database.models import CollectTask, TaskStatus
from backend.services.task_service import check_task_status
import logging

# Configure logging
logging.basicConfig()
logger = logging.getLogger("scheduler")
logger.setLevel(logging.INFO)

scheduler = BackgroundScheduler()

def check_all_tasks():
    """
    Periodic job to check status of all relevant tasks.
    """
    logger.info("Running scheduled task check...")
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        # Query tasks that might need status updates
        # We check DRAFT (to activate), ACTIVE (to close), and AGGREGATED (to re-aggregate)
        tasks = db.query(CollectTask).filter(
            CollectTask.status.in_([
                TaskStatus.DRAFT, 
                TaskStatus.ACTIVE, 
                TaskStatus.AGGREGATED
            ])
        ).all()
        
        for task in tasks:
            try:
                check_task_status(task, db)
            except Exception as e:
                logger.error(f"Error checking task {task.id}: {e}")
                
    except Exception as e:
        logger.error(f"Scheduler job failed: {e}")
    finally:
        db.close()

def start_scheduler():
    """
    Start the background scheduler.
    """
    if not scheduler.running:
        # Add job to run every minute
        scheduler.add_job(
            check_all_tasks,
            trigger=IntervalTrigger(minutes=1),
            id='check_task_status_job',
            name='Check Task Status and Auto-Aggregate',
            replace_existing=True
        )
        scheduler.start()
        logger.info("Background scheduler started.")

def stop_scheduler():
    """
    Stop the background scheduler.
    """
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Background scheduler stopped.")
