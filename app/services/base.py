from abc import ABC, abstractmethod
from typing import Any
from app.core.logging import get_logger

logger = get_logger("base_service")


class BaseService(ABC):
    """Abstract base class for all external service adapters"""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = get_logger(f"service.{name}")
    
    @abstractmethod
    async def health_check(self) -> dict:
        """Check if service is healthy"""
        pass
    
    @abstractmethod
    async def initialize(self):
        """Initialize service connections"""
        pass
    
    @abstractmethod
    async def shutdown(self):
        """Cleanup service connections"""
        pass
    
    def get_name(self) -> str:
        return self.name
