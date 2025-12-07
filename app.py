import sys
import os
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.logger import get_logger, init_logger

# Initialize logger configuration immediately
init_logger()

from backend.storage_service import ensure_minio_running
from backend.database.reset_db import reset_database
from backend.storage_service.reset_minio import reset_minio
from backend.database.set_default import set_default
from backend.api import auth, dashboard, emails, tasks, teachers, templates, aggregations, settings, mailbox, files, agent
from backend.scheduler import start_scheduler, stop_scheduler

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI app.
    Handles startup and shutdown events.
    """
    # Startup: Start the background scheduler
    start_scheduler()
    yield
    # Shutdown: Stop the background scheduler
    stop_scheduler()

def main():
    separator = "=" * 60
    
    # 0. Check Services (PostgreSQL & MinIO)
    print(separator)
    print("🔧 Checking Services Status...\n")
    try:
        # Check MinIO
        ensure_minio_running()
        logger.info("MinIO service is running.")
        
        # Check PostgreSQL
        from backend.database.db_config import test_connection
        success, msg = test_connection()
        if success:
            logger.info("PostgreSQL service is running.")
        else:
            raise Exception(f"PostgreSQL check failed: {msg}")
            
    except Exception as e:
        logger.error(f"Service check failed: {e}")
        sys.exit(1)
    print(separator + "\n")

    # 1. Check Resources (Database & Bucket)
    print(separator)
    print("🔍 Checking Resources Existence...\n")
    try:
        from backend.storage_service.minio_service import ensure_bucket_exists
        from backend.database.db_config import ensure_database_exists
        
        ensure_bucket_exists()
        ensure_database_exists()
        logger.info("Resources checked.")
    except Exception as e:
        logger.error(f"Resource check failed: {e}")
        sys.exit(1)
    print(separator + "\n")

    # 2. Reset Database & Storage (if --reset)
    if "--reset" in sys.argv:
        print(separator)
        print("🔄 Resetting Database & Storage...\n")
        try:
            # Skip checks since we already performed them in Step 0
            reset_database()
            reset_minio()
            logger.info("Database and storage reset complete.")
        except Exception as e:
            logger.error(f"Error resetting database: {e}")
            sys.exit(1)
        print(separator + "\n")

    # 3. Set Default Data (if --set-default AND --reset)
    if "--set-default" in sys.argv:
        if "--reset" in sys.argv:
            print(separator)
            print("📥 Inserting Default Data...\n")
            try:
                # No need to ensure_minio_running again as we checked in Step 0
                set_default()
                logger.info("Successfully inserted default data.")
            except Exception as e:
                logger.error(f"Error inserting default data: {e}")
                sys.exit(1)
            print(separator + "\n")
        else:
            logger.warning("Skipping --set-default: It requires --reset to be set.")
            print(separator + "\n")

    # 4. Initialize Application
    print(separator)
    print("🚀 Initializing Application...\n")
    try:
        # Create FastAPI app
        app = FastAPI(title="EduDataAggregator System API", lifespan=lifespan)

        # CORS
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Include Routers
        app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
        app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
        app.include_router(emails.router, prefix="/api/emails", tags=["Emails"])
        app.include_router(tasks.router, prefix="/api/tasks", tags=["Tasks"])
        app.include_router(teachers.router, prefix="/api/teachers", tags=["Teachers"])
        app.include_router(templates.router, prefix="/api/templates", tags=["Templates"])
        app.include_router(aggregations.router, prefix="/api/aggregations", tags=["Aggregations"])
        app.include_router(settings.router, prefix="/api/settings", tags=["Settings"])
        app.include_router(mailbox.router, prefix="/api/mailbox", tags=["Mailbox"])
        app.include_router(files.router, prefix="/api/files", tags=["Files"])
        app.include_router(agent.router, prefix="/api/agent", tags=["Agent"])

        # Mount Frontend
        frontend_path = os.path.join(os.path.dirname(__file__), "frontend")
        if os.path.exists(frontend_path):
            app.mount("/frontend", StaticFiles(directory=frontend_path, html=True), name="frontend")
            
            @app.get("/")
            async def root():
                return RedirectResponse(url="/frontend/index.html")
        else:
            logger.warning("Frontend directory not found.")
            
        logger.info("Application initialized successfully.")
    except Exception as e:
        logger.error(f"Application initialization failed: {e}")
        sys.exit(1)
    print(separator + "\n")

    # 5. Run Server
    print(separator)
    print("🚀 Starting server on http://localhost:8000\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
    print(separator + "\n")

if __name__ == "__main__":
    main()
