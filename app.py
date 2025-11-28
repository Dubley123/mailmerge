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

from backend.storage_service import ensure_minio_running
from backend.database.reset_db import reset_database
from backend.database.set_default import set_default
from backend.api import auth, dashboard, emails, tasks, teachers, templates, aggregations, settings
from backend.scheduler import start_scheduler, stop_scheduler

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
    # 1. Check for --reset and/or --set-default
    if "--reset" in sys.argv:
        print("🔄 Resetting database and storage...")
        print("=" * 60)
        print("DATABASE & STORAGE RESET")
        print("=" * 60)
        try:
            reset_database()
            print("✅ Database and storage reset complete.")
        except Exception as e:
            print(f"❌ Error resetting database: {e}")
            sys.exit(1)
        
        print("\n" + "=" * 60)
        print("DATABASE & STORAGE RESET COMPLETE")
        print("=" * 60)

    # Support separate set-default operation
    if "--set-default" in sys.argv:
        print("🔄 Inserting default data into database...")
        print("=" * 60)
        print("SET DEFAULT DATA")
        print("=" * 60)
        try:
            # ensure MinIO is running before uploading attachments
            ensure_minio_running()
            set_default()
            print("✅ Successfully inserted default data.")
        except Exception as e:
            print(f"❌ Error inserting default data: {e}")
            sys.exit(1)
            
        print("=" * 60)
        print("SET DEFAULT DATA COMPLETE")
        print("=" * 60)

    # 2. Ensure MinIO and database are initialized
    print("🔧 Initializing services...")
    try:
        # Start MinIO service
        ensure_minio_running()
        
        # Ensure bucket exists
        from backend.storage_service.minio_service import ensure_bucket_exists
        ensure_bucket_exists()
        
        # Ensure database exists
        from backend.database.db_config import ensure_database_exists
        ensure_database_exists()
        
        print("✅ Services initialized successfully")
    except Exception as e:
        print(f"❌ Service initialization failed: {e}")
        sys.exit(1)

    # 3. Create FastAPI app
    app = FastAPI(title="MailMerge System API", lifespan=lifespan)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 4. Include Routers
    app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
    app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
    app.include_router(emails.router, prefix="/api/emails", tags=["Emails"])
    app.include_router(tasks.router, prefix="/api/tasks", tags=["Tasks"])
    app.include_router(teachers.router, prefix="/api/teachers", tags=["Teachers"])
    app.include_router(templates.router, prefix="/api/templates", tags=["Templates"])
    app.include_router(aggregations.router, prefix="/api/aggregations", tags=["Aggregations"])
    app.include_router(settings.router, prefix="/api/settings", tags=["Settings"])

    # 5. Mount Frontend
    frontend_path = os.path.join(os.path.dirname(__file__), "frontend")
    if os.path.exists(frontend_path):
        app.mount("/frontend", StaticFiles(directory=frontend_path, html=True), name="frontend")
        
        @app.get("/")
        async def root():
            return RedirectResponse(url="/frontend/index.html")
    else:
        print("⚠️ Warning: Frontend directory not found.")

    # 6. Run Uvicorn
    print("🚀 Starting server on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()
