from app.services.base import BaseService
from app.infrastructure.http_client import HttpClient
from app.infrastructure.circuit_breaker import CircuitBreakerRegistry
from app.core.config import get_settings
from app.core.logging import get_logger
from urllib.parse import urlencode

settings = get_settings()
logger = get_logger("oauth_handler")


class OAuthHandler(BaseService):
    """OAuth 2.0 handler for Bungie.net authentication"""
    
    def __init__(self):
        super().__init__("oauth")
        self.client = HttpClient(
            base_url="https://www.bungie.net",
            timeout=30
        )
        self.circuit_breaker = CircuitBreakerRegistry.get("oauth")
    
    async def initialize(self):
        logger.info("OAuth handler initialized")
    
    async def shutdown(self):
        await self.client.close()
        logger.info("OAuth handler shutdown")
    
    async def health_check(self) -> dict:
        return {"status": "healthy"}
    
    def get_auth_url(self, state: str = None) -> str:
        """Generate OAuth authorization URL"""
        params = {
            "client_id": settings.bungie_client_id,
            "response_type": "code",
            "state": state or "helix_state"
        }
        
        auth_url = f"{settings.bungie_oauth_url}?{urlencode(params)}"
        logger.info(f"Generated OAuth URL: {auth_url}")
        return auth_url
    
    async def exchange_code_for_token(self, code: str) -> dict:
        """Exchange authorization code for access token"""
        try:
            return await self.circuit_breaker.call(
                self._exchange_code,
                code
            )
        except Exception as e:
            logger.error(f"OAuth token exchange failed: {e}")
            raise
    
    async def _exchange_code(self, code: str) -> dict:
        """Internal method to exchange code for token"""
        data = {
            "client_id": settings.bungie_client_id,
            "client_secret": settings.bungie_client_secret,
            "grant_type": "authorization_code",
            "code": code
        }
        
        response = await self.client.post(
            "/platform/app/oauth/token/",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if response.status_code != 200:
            raise Exception(f"OAuth exchange failed: {response.status_code}")
        
        return response.json()
    
    async def refresh_token(self, refresh_token: str) -> dict:
        """Refresh access token using refresh token"""
        try:
            return await self.circuit_breaker.call(
                self._refresh_token,
                refresh_token
            )
        except Exception as e:
            logger.error(f"OAuth token refresh failed: {e}")
            raise
    
    async def _refresh_token(self, refresh_token: str) -> dict:
        """Internal method to refresh token"""
        data = {
            "client_id": settings.bungie_client_id,
            "client_secret": settings.bungie_client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        }
        
        response = await self.client.post(
            "/platform/app/oauth/token/",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if response.status_code != 200:
            raise Exception(f"OAuth refresh failed: {response.status_code}")
        
        return response.json()


# Global OAuth handler instance
oauth_handler = OAuthHandler()


def get_oauth_handler() -> OAuthHandler:
    """Get global OAuth handler instance"""
    return oauth_handler
