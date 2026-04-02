from typing import TypeVar, Type
from app.services.base import BaseService
from app.core.logging import get_logger

logger = get_logger("service_registry")

T = TypeVar("T", bound=BaseService)


class ServiceRegistry:
    """Service discovery and registry for SOA architecture"""
    
    _services: dict[str, BaseService] = {}
    
    @classmethod
    def register(cls, service: BaseService):
        name = service.get_name()
        cls._services[name] = service
        logger.info(f"Registered service: {name}")
    
    @classmethod
    def get(cls, name: str) -> BaseService | None:
        return cls._services.get(name)
    
    @classmethod
    def get_all(cls) -> dict[str, BaseService]:
        return cls._services.copy()
    
    @classmethod
    async def initialize_all(cls):
        """Initialize all registered services"""
        for name, service in cls._services.items():
            try:
                await service.initialize()
                logger.info(f"Initialized service: {name}")
            except Exception as e:
                logger.error(f"Failed to initialize {name}: {e}")
    
    @classmethod
    async def shutdown_all(cls):
        """Shutdown all registered services"""
        for name, service in cls._services.items():
            try:
                await service.shutdown()
                logger.info(f"Shutdown service: {name}")
            except Exception as e:
                logger.error(f"Error shutting down {name}: {e}")
    
    @classmethod
    async def health_check_all(cls) -> dict[str, dict]:
        """Check health of all services"""
        results = {}
        for name, service in cls._services.items():
            try:
                results[name] = await service.health_check()
            except Exception as e:
                results[name] = {"status": "unhealthy", "error": str(e)}
        return results
