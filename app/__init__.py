"""
Helix Backend - Modular SOA with External API Orchestration

Architecture:
- Core Layer: Configuration, logging, exceptions
- Infrastructure Layer: HTTP client, circuit breaker, caching
- Service Layer: Adapters for external APIs (Bungie, Telegram)
- API Layer: FastAPI endpoints (webhook, health)
- Orchestrator: Coordinates multi-service workflows
"""

__version__ = "0.1.0"
