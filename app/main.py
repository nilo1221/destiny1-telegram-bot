from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import asyncio

from app.api.v1.router import router as v1_router
from app.api.v1.endpoints.webhook import init_orchestrator, shutdown_orchestrator
from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.adapters import TelegramAdapter
from app.core.d1_event_notifier import init_notifier

settings = get_settings()
logger = get_logger("main")

# Task per lo scheduler notifiche
event_notifier_task = None

async def start_event_notifier_scheduler():
    """Avvia lo scheduler notifiche eventi in background"""
    global event_notifier_task
    try:
        telegram = TelegramAdapter()
        notifier = init_notifier(telegram)
        event_notifier_task = asyncio.create_task(
            notifier.start_scheduler(check_interval_seconds=60)
        )
        logger.info("[Main] Scheduler notifiche eventi avviato")
    except Exception as e:
        logger.error(f"[Main] Errore avvio scheduler notifiche: {e}")

async def stop_event_notifier_scheduler():
    """Ferma lo scheduler notifiche"""
    global event_notifier_task
    try:
        from app.core.d1_event_notifier import d1_event_notifier
        if d1_event_notifier:
            d1_event_notifier.stop_scheduler()
        if event_notifier_task:
            event_notifier_task.cancel()
            try:
                await event_notifier_task
            except asyncio.CancelledError:
                pass
        logger.info("[Main] Scheduler notifiche eventi fermato")
    except Exception as e:
        logger.error(f"[Main] Errore stop scheduler notifiche: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info(f"Starting {settings.app_name}...")
    await init_orchestrator()
    
    # Avvia scheduler notifiche eventi
    await start_event_notifier_scheduler()
    
    logger.info(f"{settings.app_name} started successfully")
    
    yield
    
    # Shutdown
    logger.info(f"Shutting down {settings.app_name}...")
    await stop_event_notifier_scheduler()

app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description="Helix Destiny 1 Bot API"
)

app.include_router(v1_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {
        "service": settings.APP_NAME,
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs"
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}

# Vercel serverless handler
def handler(request):
    return app(request)
