class HelixException(Exception):
    """Base exception for Helix backend"""
    pass


class ServiceUnavailableError(HelixException):
    """External service is unavailable"""
    pass


class AuthenticationError(HelixException):
    """Authentication failed"""
    pass


class RateLimitError(HelixException):
    """Rate limit exceeded"""
    pass


class CircuitBreakerOpenError(HelixException):
    """Circuit breaker is open"""
    pass


class PlayerNotFoundError(HelixException):
    """Player not found in Bungie API"""
    pass


class CommandError(HelixException):
    """Command execution error"""
    pass
