import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.exceptions import ServiceUnavailableError, RateLimitError

settings = get_settings()
logger = get_logger("http_client")


class HttpClient:
    """Async HTTP client with retry logic and connection pooling"""
    
    def __init__(self, base_url: str = "", headers: dict = None, timeout: int = 30):
        self.base_url = base_url
        self.headers = headers or {}
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self.headers,
                timeout=self.timeout,
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=50)
            )
        return self._client
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError)),
        reraise=True
    )
    async def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        client = await self._get_client()
        full_url = f"{self.base_url}{url}" if self.base_url else url
        
        logger.debug(f"HTTP {method} {full_url}")
        
        try:
            response = await client.request(method, url, **kwargs)
            
            if response.status_code == 429:
                raise RateLimitError(f"Rate limit exceeded for {full_url}")
            
            if response.status_code >= 500:
                raise ServiceUnavailableError(f"Service unavailable: {response.status_code}")
            
            response.raise_for_status()
            return response
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Request failed: {str(e)}")
            raise ServiceUnavailableError(f"Request to {full_url} failed: {str(e)}")
    
    async def get(self, url: str, **kwargs) -> httpx.Response:
        return await self.request("GET", url, **kwargs)
    
    async def post(self, url: str, **kwargs) -> httpx.Response:
        return await self.request("POST", url, **kwargs)
    
    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
