"""
Background Scheduler
Handles periodic tasks such as checking task status and auto-aggregation.
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from backend.database.db_config import get_session_factory
from backend.database.models import CollectTask, TaskStatus
from backend.utils.tasks_utils import check_task_status
from backend.email_service.email_receiver import fetch_and_process_emails
import uuid
import time
import os
import yaml
from datetime import datetime, timezone
from backend.utils.time_utils import ensure_utc
from .utils import read_last_fetch_timestamp, write_last_fetch_timestamp
from backend.logger import get_logger

logger = get_logger("scheduler")

scheduler = BackgroundScheduler()

class JobLogger:
    def __init__(self, job_name):
        self.job_name = job_name
        self.run_id = str(uuid.uuid4())[:8]
        self.start_time = time.time()
        self.steps = []
        self.stats = {}

    def log_step(self, message):
        self.steps.append(message)

    def set_stat(self, key, value):
        self.stats[key] = value

    def finish(self, error=None):
        duration = time.time() - self.start_time
        start_dt = datetime.fromtimestamp(self.start_time, tz=timezone.utc).isoformat()
        
        separator = "=" * 60
        
        lines = []
        lines.append(separator)
        lines.append(f"SCHEDULER JOB: {self.job_name}")
        lines.append(f"ID: {self.run_id} | START: {start_dt}")
        lines.append("-" * 60)
        
        for idx, step in enumerate(self.steps, 1):
            lines.append(f"[{idx}] {step}")
            
        if self.stats:
            lines.append("-" * 60)
            stats_str = ", ".join(f"{k}: {v}" for k, v in self.stats.items())
            lines.append(f"[STATS] {stats_str}")
            
        if error:
            lines.append("-" * 60)
            lines.append(f"[ERROR] {str(error)}")
            
        lines.append(f"END JOB | DURATION: {duration:.2f}s")
        lines.append(separator)
        
        logger.info("\n" + "\n".join(lines) + "\n")

def check_all_tasks():
    """
    Periodic job to check status of all relevant tasks.
    """
    job_log = JobLogger("Check Task Status")
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        job_log.log_step("Querying tasks (DRAFT, ACTIVE, AGGREGATED)...")
        tasks = db.query(CollectTask).filter(
            CollectTask.status.in_([
                TaskStatus.DRAFT, 
                TaskStatus.ACTIVE, 
                TaskStatus.AGGREGATED
            ])
        ).all()
        
        job_log.set_stat("tasks_found", len(tasks))
        
        updated_count = 0
        for task in tasks:
            try:
                job_log.log_step(f"Checking Task ID {task.id} ({task.name}) - Status: {task.status}")
                check_task_status(task, db, logger=job_log.log_step)
                updated_count += 1
            except Exception as e:
                job_log.log_step(f"Error checking task {task.id}: {e}")
                
        job_log.set_stat("tasks_checked", updated_count)
        job_log.finish()
                
    except Exception as e:
        job_log.finish(error=e)
    finally:
        db.close()

def fetch_emails_job():
    """
    Periodic job to fetch and process emails.
    """
    job_log = JobLogger("Fetch Emails")
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        # Read last fetch timestamp (UTC)
        last_ts = read_last_fetch_timestamp()
        job_log.log_step(f"Last fetch timestamp: {last_ts}")
        
        # fetch emails newer than last_ts; function returns (latest timestamp seen, count)
        latest_ts, count = fetch_and_process_emails(db, since_ts=last_ts, logger=job_log.log_step)
        
        job_log.set_stat("emails_processed", count)
        if latest_ts:
            job_log.set_stat("latest_ts_seen", latest_ts.isoformat())
        
        if latest_ts:
            # Convert to Beijing Time for logging consistency
            latest_ts_bj = ensure_utc(latest_ts)
            job_log.log_step(f"Updating last fetch timestamp to {latest_ts_bj}")
            write_last_fetch_timestamp(latest_ts)
        else:
            job_log.log_step("No new emails found or no timestamp update needed.")
            
        job_log.finish()
            
    except Exception as e:
        job_log.finish(error=e)
    finally:
        db.close()

def load_config():
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../config.yaml'))
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return {}

def start_scheduler():
    """
    Start the background scheduler.
    """
    if not scheduler.running:
        config = load_config()
        scheduler_config = config.get("SCHEDULER", {})
        email_interval = scheduler_config.get("EMAIL_INTERVAL", 30)
        task_interval = scheduler_config.get("TASK_INTERVAL", 30)

        # Add job to check task status
        scheduler.add_job(
            check_all_tasks,
            trigger=IntervalTrigger(seconds=task_interval),
            id='check_task_status_job',
            name='Check Task Status and Auto-Aggregate',
            replace_existing=True
        )
        
        # Add job to fetch emails
        scheduler.add_job(
            fetch_emails_job,
            trigger=IntervalTrigger(seconds=email_interval),
            id='fetch_emails_job',
            name='Fetch and Process Emails',
            replace_existing=True
        )
        
        scheduler.start()
        logger.info(f"Background scheduler started. Task Interval: {task_interval}s, Email Interval: {email_interval}s")

def stop_scheduler():
    """
    Stop the background scheduler.
    """
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Background scheduler stopped.")
