from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from contextlib import asynccontextmanager
from src.constant.config import settings
from src.util.database import init_db
from src.services.rss_service import rss_service
from src.services.report_service import report_service
from src.services.storage_service import storage_service
from src.util.logger import logger
import pytz
import secrets

# Scheduler setup
scheduler = AsyncIOScheduler(timezone=pytz.timezone('Asia/Shanghai'))
security = HTTPBasic()

def verify_admin(credentials: HTTPBasicCredentials = Depends(security)):
    is_correct_password = secrets.compare_digest(credentials.password, settings.ADMIN_PASSWORD)
    if not is_correct_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

def job_fetch_rss():
    logger.info("Starting scheduled RSS fetch job...")
    urls = [url.strip() for url in settings.RSS_URLS.split(",") if url.strip()]
    if not urls:
        logger.warning("No RSS URLs configured.")
        return
    
    for url in urls:
        rss_service.fetch_and_process_feed(url)
    logger.info("RSS fetch job completed.")

def job_daily_report():
    logger.info("Starting scheduled daily report job...")
    report_service.send_daily_report()
    logger.info("Daily report job completed.")

def job_cleanup():
    logger.info("Starting monthly cleanup job...")
    storage_service.cleanup_old_files(days=30)
    logger.info("Cleanup job completed.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Application startup")
    init_db()
    
    # Add jobs
    # 1. Fetch RSS every hour
    scheduler.add_job(job_fetch_rss, IntervalTrigger(hours=1), id="fetch_rss", replace_existing=True)
    
    # 2. Daily Report at 09:00 Beijing Time

    hour, minute = map(int, settings.PUSH_TIME.split(":"))
    scheduler.add_job(job_daily_report, CronTrigger(hour=hour, minute=minute, timezone='Asia/Shanghai'), id="daily_report", replace_existing=True)

    # 3. Cleanup Job (Monxthly, e.g., 1st day of month at 03:00)
    scheduler.add_job(job_cleanup, CronTrigger(day=1, hour=3, minute=0, timezone='Asia/Shanghai'), id="cleanup", replace_existing=True)

    scheduler.start()
    yield
    
    # Shutdown
    logger.info("Application shutdown")
    scheduler.shutdown()

app = FastAPI(title="CrawlWess RSS Agent", lifespan=lifespan)

@app.get("/")
def read_root():
    return {"status": "running", "timezone": "Asia/Shanghai"}

from pydantic import BaseModel

# --- Debug Endpoints ---

class FetchRequest(BaseModel):
    url: str | None = None

@app.post("/debug/fetch", dependencies=[Depends(verify_admin)])
async def debug_fetch(request: FetchRequest = None):
    """Trigger RSS fetch immediately (Authenticated). Optional: provide specific 'url'."""
    if request and request.url:
        logger.info(f"Triggering manual fetch for: {request.url}")
        scheduler.add_job(rss_service.fetch_and_process_feed, args=[request.url])
        return {"message": f"RSS fetch job triggered for {request.url}"}
    else:
        logger.info("Triggering configured RSS fetch job")
        scheduler.add_job(job_fetch_rss)
        return {"message": "RSS fetch job triggered for all configured URLs"}

@app.post("/debug/report", dependencies=[Depends(verify_admin)])
async def debug_report():
    """Trigger Daily Report immediately (Authenticated)"""
    scheduler.add_job(job_daily_report)
    return {"message": "Daily report job triggered"}

@app.post("/debug/cleanup", dependencies=[Depends(verify_admin)])
async def debug_cleanup():
    """Trigger Cleanup immediately (Authenticated)"""
    scheduler.add_job(job_cleanup)
    return {"message": "Cleanup job triggered"}

@app.post("/debug/full-flow", dependencies=[Depends(verify_admin)])
async def debug_full_flow():
    """Trigger Full Flow: Fetch -> Report (Authenticated)"""
    # Chain them or just add both? Adding both puts them in queue.
    # APScheduler runs in thread pool, order might not be strict if pool size > 1.
    # But usually fine. Or define a sequence job.
    
    def full_flow():
        job_fetch_rss()
        job_daily_report()
        
    scheduler.add_job(full_flow)
    return {"message": "Full flow (Fetch -> Report) triggered"}
