"""
Vendor type definitions for wearable integrations.
"""

from enum import Enum


class VendorType(str, Enum):
    """Wearable vendor types supported by Synheart."""

    WHOOP = "whoop"
    GARMIN = "garmin"
    FITBIT = "fitbit"

    def __str__(self) -> str:
        """Return the string value of the enum."""
        return self.value

    @classmethod
    def is_valid(cls, vendor: str) -> bool:
        """Check if a vendor string is valid."""
        try:
            cls(vendor)
            return True
        except ValueError:
            return False

    @classmethod
    def list_vendors(cls) -> list[str]:
        """List all available vendor types."""
        return [v.value for v in cls]
