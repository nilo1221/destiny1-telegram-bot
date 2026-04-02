from fastapi import APIRouter
from .endpoints import webhook, health, oauth

router = APIRouter()

# Include all endpoint routers
router.include_router(health.router, tags=["health"])
router.include_router(webhook.router, prefix="/webhook", tags=["webhook"])
router.include_router(oauth.router, prefix="/oauth", tags=["oauth"])
