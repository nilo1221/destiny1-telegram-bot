import os
from dotenv import load_dotenv
from typing import Optional


class Settings:
    def __init__(self):
        # Carica le variabili d'ambiente
        load_dotenv()
        
        # Basic settings
        self.app_name = os.getenv("APP_NAME", "Helix")
        self.debug = os.getenv("DEBUG", "False").lower() == "true"
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        
        # Telegram settings
        self.telegram_token = os.getenv("TELEGRAM_TOKEN")
        
        # Bungie API settings
        self.bungie_api_key = os.getenv("BUNGIE_API_KEY")
        self.bungie_client_id = int(os.getenv("BUNGIE_CLIENT_ID", "0"))
        self.bungie_client_secret = os.getenv("BUNGIE_CLIENT_SECRET")
        self.bungie_oauth_url = os.getenv("BUNGIE_OAUTH_URL", "https://www.bungie.net/it/OAuth/Authorize")
        self.bungie_base_url = os.getenv("BUNGIE_BASE_URL", "https://www.bungie.net/Platform")
        
        # Cache settings
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.cache_ttl = int(os.getenv("CACHE_TTL", "300"))
        
        # Server settings
        self.host = os.getenv("HOST", "0.0.0.0")
        self.port = int(os.getenv("PORT", "8000"))
        self.webhook_url = os.getenv("WEBHOOK_URL")
        
        # Security settings - REQUIRED for OAuth
        self.token_encryption_key = os.getenv("TOKEN_ENCRYPTION_KEY")


def get_settings() -> Settings:
    return Settings()
