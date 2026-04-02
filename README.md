# Helix Backend

**Modular SOA Backend with External API Orchestration for Destiny 2**

## Architecture

```
helix-backend/
├── app/
│   ├── core/              # Configuration, logging, exceptions
│   ├── infrastructure/    # HTTP client, circuit breaker, cache
│   ├── services/          # Service adapters & orchestrator
│   │   └── adapters/      # Bungie API, Telegram API
│   └── api/               # FastAPI endpoints
│       └── v1/endpoints/  # Webhook, health
```

## Quick Start

### 1. Install dependencies

```bash
# Using Poetry (recommended)
poetry install

# Or using pip
pip install fastapi uvicorn httpx tenacity redis pydantic pydantic-settings python-dotenv structlog
```

### 2. Configure environment

`.env` file (already configured):
```env
TELEGRAM_TOKEN=your_bot_token
BUNGIE_API_KEY=your_api_key
BUNGIE_CLIENT_ID=your_client_id
BUNGIE_CLIENT_SECRET=your_client_secret
REDIS_URL=redis://localhost:6379
```

### 3. Start Redis (optional, for caching)

```bash
docker run -d -p 6379:6379 redis:alpine
```

### 4. Run the server

```bash
# Development
poetry run python run.py

# Production
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Service info |
| `/health` | GET | Health check |
| `/health/detailed` | GET | Detailed health with service status |
| `/api/v1/webhook/telegram` | POST | Telegram bot webhook |

## Bot Commands

- `/start` - Welcome message
- `/help` - Show available commands
- `/find <gamertag>` - Search Destiny 2 player
- `/activities <gamertag>` - Show recent activities

## Features

- **SOA Architecture**: Modular service adapters
- **Resilience**: Circuit breaker + retry logic
- **Caching**: Redis layer for API responses
- **Health Monitoring**: Detailed service health checks
- **Structured Logging**: JSON logging with structlog

## Docker

```bash
docker-compose up -d
```

This starts:
- Helix API on port 8000
- Redis on port 6379

## Architecture Patterns

- **Adapter Pattern**: External API abstraction
- **Circuit Breaker**: Fault tolerance
- **Service Registry**: Service discovery
- **Orchestrator**: Multi-service workflow coordination
