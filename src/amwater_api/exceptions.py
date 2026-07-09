"""Exceptions for the American Water API."""

class AmericanWaterError(Exception):
    """Base exception for American Water API."""
    pass

class AmericanWaterAuthError(AmericanWaterError):
    """Exception raised when authentication fails (e.g. invalid credentials)."""
    pass

class AmericanWaterConnectError(AmericanWaterError):
    """Exception raised when connection or HTTP errors occur."""
    pass
