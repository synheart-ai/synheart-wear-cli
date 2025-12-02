"""Synheart Cloud Connector - Shared base library for cloud wearable integrations."""

from .base import CloudConnectorBase
from .exceptions import (
    CloudConnectorError,
    OAuthError,
    RateLimitError,
    TokenError,
    WebhookError,
)
from .sync_state import SyncCursor, SyncState
from .vendor_types import (
    EventType,
    OAuthTokens,
    TokenStatus,
    VendorType,
    WebhookEvent,
)

__version__ = "0.1.1"

__all__ = [
    "CloudConnectorBase",
    "CloudConnectorError",
    "OAuthError",
    "TokenError",
    "WebhookError",
    "RateLimitError",
    "VendorType",
    "TokenStatus",
    "EventType",
    "OAuthTokens",
    "WebhookEvent",
    "SyncState",
    "SyncCursor",
]
