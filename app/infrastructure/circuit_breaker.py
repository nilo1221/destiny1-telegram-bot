import asyncio
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta
from app.core.logging import get_logger
from app.core.exceptions import CircuitBreakerOpenError

logger = get_logger("circuit_breaker")


class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    recovery_timeout: int = 30
    half_open_max_calls: int = 3


class CircuitBreaker:
    """Circuit breaker pattern for resilient service calls"""
    
    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.last_failure_time: datetime | None = None
        self.half_open_calls = 0
        self._lock = asyncio.Lock()
    
    async def call(self, func, *args, **kwargs):
        async with self._lock:
            await self._check_state()
            
            if self.state == CircuitState.OPEN:
                raise CircuitBreakerOpenError(f"Circuit breaker {self.name} is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            await self._record_success()
            return result
        except Exception as e:
            await self._record_failure()
            raise
    
    async def _check_state(self):
        if self.state == CircuitState.OPEN:
            if self.last_failure_time and \
               datetime.utcnow() - self.last_failure_time > timedelta(seconds=self.config.recovery_timeout):
                logger.info(f"Circuit {self.name}: Transitioning to HALF_OPEN")
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
    
    async def _record_success(self):
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.half_open_calls += 1
                if self.half_open_calls >= self.config.half_open_max_calls:
                    logger.info(f"Circuit {self.name}: Transitioning to CLOSED")
                    self._reset()
            else:
                self._reset()
    
    async def _record_failure(self):
        async with self._lock:
            self.failures += 1
            self.last_failure_time = datetime.utcnow()
            
            if self.state == CircuitState.HALF_OPEN:
                logger.warning(f"Circuit {self.name}: Failed in HALF_OPEN, transitioning to OPEN")
                self.state = CircuitState.OPEN
            elif self.failures >= self.config.failure_threshold:
                logger.error(f"Circuit {self.name}: Failure threshold reached, transitioning to OPEN")
                self.state = CircuitState.OPEN
    
    def _reset(self):
        self.failures = 0
        self.state = CircuitState.CLOSED
        self.half_open_calls = 0
        self.last_failure_time = None
    
    def get_state(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "failures": self.failures,
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None
        }


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers"""
    
    _breakers: dict[str, CircuitBreaker] = {}
    
    @classmethod
    def get(cls, name: str) -> CircuitBreaker:
        if name not in cls._breakers:
            cls._breakers[name] = CircuitBreaker(name)
        return cls._breakers[name]
    
    @classmethod
    def get_all_states(cls) -> list[dict]:
        return [breaker.get_state() for breaker in cls._breakers.values()]
