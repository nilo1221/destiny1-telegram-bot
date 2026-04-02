from fastapi import APIRouter
from app.services.registry import ServiceRegistry
from app.infrastructure.circuit_breaker import CircuitBreakerRegistry

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check"""
    return {
        "status": "healthy",
        "service": "helix-backend",
        "version": "0.1.0"
    }


@router.get("/health/detailed")
async def detailed_health():
    """Detailed health with service status"""
    service_health = await ServiceRegistry.health_check_all()
    circuit_states = CircuitBreakerRegistry.get_all_states()
    
    all_healthy = all(
        s.get("status") == "healthy" for s in service_health.values()
    )
    
    return {
        "status": "healthy" if all_healthy else "degraded",
        "services": service_health,
        "circuit_breakers": circuit_states
    }


@router.get("/ready")
async def readiness_check():
    """Kubernetes readiness probe"""
    return {"ready": True}
