from pydantic_settings import BaseSettings, Field
from functools import lru_cache


class Settings(BaseSettings):
    # Telegram
    
    # Telegram settings
    telegram_token: str = Field(...)
    
    # Bungie API settings
    bungie_api_key: str = Field(...)
    bungie_client_id: int = Field(...)
    bungie_client_secret: str = Field(...)
    bungie_oauth_url: str = Field(default="https://www.bungie.net/it/OAuth/Authorize")
    bungie_base_url: str = Field(default="https://www.bungie.net/Platform")
    
    # Cache settings
    redis_url: str = Field(default="redis://localhost:6379")
    cache_ttl: int = Field(default=300)
    
    # Server settings
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    webhook_url: Optional[str] = Field(default=None)
    
    # Security settings - REQUIRED for OAuth
    token_encryption_key: str = Field(..., description="Encryption key for OAuth tokens")
    
    class Config:
        env_file = ".env"
        case_sensitive = True


def get_settings() -> Settings:
    return Settings()
