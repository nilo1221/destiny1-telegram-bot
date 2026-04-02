from app.services.base import BaseService
from app.infrastructure.http_client import HttpClient
from app.infrastructure.circuit_breaker import CircuitBreakerRegistry
from app.core.config import get_settings
from app.core.exceptions import ServiceUnavailableError
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger("telegram_adapter")


class TelegramAdapter(BaseService):
    """Adapter for Telegram Bot API with circuit breaker"""
    
    def __init__(self):
        super().__init__("telegram")
        self.token = settings.telegram_token
        self.client = HttpClient(
            base_url=f"https://api.telegram.org/bot{self.token}",
            timeout=30
        )
        self.circuit_breaker = CircuitBreakerRegistry.get("telegram")
    
    async def initialize(self):
        # Set webhook if configured
        if settings.webhook_url:
            await self.set_webhook(settings.webhook_url)
        logger.info("Telegram adapter initialized")
    
    async def shutdown(self):
        await self.client.close()
        logger.info("Telegram adapter shutdown")
    
    async def health_check(self) -> dict:
        try:
            me = await self.get_me()
            return {"status": "healthy", "bot_username": me.get("username", "unknown")}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    async def get_me(self) -> dict:
        """Get bot info"""
        result = await self.circuit_breaker.call(self._make_request, "get", "/getMe")
        return result.get("result", {})
    
    async def send_message(self, chat_id: int, text: str, parse_mode: str = "HTML") -> dict:
        """Send message to chat"""
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode
        }
        
        return await self.circuit_breaker.call(
            self._make_request,
            "post",
            "/sendMessage",
            json=payload
        )
    
    async def set_webhook(self, url: str) -> dict:
        """Set bot webhook URL"""
        payload = {"url": url}
        result = await self._make_request("post", "/setWebhook", json=payload)
        logger.info(f"Webhook set to {url}")
        return result
    
    async def delete_webhook(self) -> dict:
        """Remove webhook"""
        return await self._make_request("post", "/deleteWebhook")
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Internal request method"""
        if method == "get":
            response = await self.client.get(endpoint, **kwargs)
        else:
            response = await self.client.post(endpoint, **kwargs)
        
        data = response.json()
        
        if not data.get("ok"):
            error = data.get("description", "Unknown error")
            raise ServiceUnavailableError(f"Telegram API error: {error}")
        
        return data
