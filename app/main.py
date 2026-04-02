from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from app.api.v1.router import router as v1_router
from app.api.v1.endpoints.webhook import init_orchestrator, shutdown_orchestrator
from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info(f"Starting {settings.app_name}...")
    await init_orchestrator()
    logger.info(f"{settings.app_name} started successfully")
    
    yield
    
    # Shutdown
    logger.info(f"Shutting down {settings.app_name}...")
    await shutdown_orchestrator()
    logger.info(f"{settings.app_name} shutdown complete")


app = FastAPI(
    title=settings.app_name,
    description="Modular SOA Backend with External API Orchestration for Destiny 2",
    version="0.1.0",
    lifespan=lifespan
)

# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include API routes
app.include_router(v1_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "service": settings.app_name,
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs"
    }
