"""Illinois American Water API package."""

__version__ = "0.1.0"

from .client import AmericanWaterAPI
from .exceptions import (
    AmericanWaterAuthError,
    AmericanWaterConnectError,
    AmericanWaterError,
)

__all__ = [
    "AmericanWaterAPI",
    "AmericanWaterError",
    "AmericanWaterAuthError",
    "AmericanWaterConnectError",
]
