import json
import redis.asyncio as redis
from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger("cache")


class Cache:
    """Redis cache layer with TTL support"""
    
    def __init__(self):
        self._redis: redis.Redis | None = None
    
    async def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(settings.redis_url, decode_responses=True)
        return self._redis
    
    async def get(self, key: str) -> any:
        try:
            r = await self._get_redis()
            value = await r.get(key)
            if value:
                logger.debug(f"Cache hit: {key}")
                return json.loads(value)
            logger.debug(f"Cache miss: {key}")
            return None
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None
    
    async def set(self, key: str, value: any, ttl: int = None):
        try:
            r = await self._get_redis()
            ttl = ttl or settings.cache_ttl
            await r.setex(key, ttl, json.dumps(value))
            logger.debug(f"Cache set: {key} (TTL: {ttl}s)")
        except Exception as e:
            logger.error(f"Cache set error: {e}")
    
    async def delete(self, key: str):
        try:
            r = await self._get_redis()
            await r.delete(key)
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
    
    async def close(self):
        if self._redis:
            await self._redis.close()


# Global cache instance
cache = Cache()
