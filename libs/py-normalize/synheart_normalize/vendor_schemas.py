"""
Vendor-specific data schemas and validation.
"""

from typing import Dict, Any, List
from abc import ABC, abstractmethod


class VendorSchema(ABC):
    """Base class for vendor-specific schemas."""

    @abstractmethod
    def validate_recovery(self, data: Dict[str, Any]) -> bool:
        """Validate recovery data format."""
        pass

    @abstractmethod
    def validate_sleep(self, data: Dict[str, Any]) -> bool:
        """Validate sleep data format."""
        pass

    @abstractmethod
    def validate_workout(self, data: Dict[str, Any]) -> bool:
        """Validate workout data format."""
        pass


class WhoopSchema(VendorSchema):
    """WHOOP API data schema validator."""

    REQUIRED_RECOVERY_FIELDS = ['id', 'user_id', 'created_at', 'score']
    REQUIRED_SLEEP_FIELDS = ['id', 'user_id', 'created_at', 'score']
    REQUIRED_WORKOUT_FIELDS = ['id', 'user_id', 'created_at', 'sport_id']

    def validate_recovery(self, data: Dict[str, Any]) -> bool:
        """Validate WHOOP recovery data."""
        return all(field in data for field in self.REQUIRED_RECOVERY_FIELDS)

    def validate_sleep(self, data: Dict[str, Any]) -> bool:
        """Validate WHOOP sleep data."""
        return all(field in data for field in self.REQUIRED_SLEEP_FIELDS)

    def validate_workout(self, data: Dict[str, Any]) -> bool:
        """Validate WHOOP workout data."""
        return all(field in data for field in self.REQUIRED_WORKOUT_FIELDS)


class GarminSchema(VendorSchema):
    """Garmin API data schema validator."""

    def validate_recovery(self, data: Dict[str, Any]) -> bool:
        """Validate Garmin recovery data."""
        # TODO: Implement based on Garmin API schema
        return True

    def validate_sleep(self, data: Dict[str, Any]) -> bool:
        """Validate Garmin sleep data."""
        # TODO: Implement based on Garmin API schema
        return True

    def validate_workout(self, data: Dict[str, Any]) -> bool:
        """Validate Garmin workout data."""
        # TODO: Implement based on Garmin API schema
        return True


class FitbitSchema(VendorSchema):
    """Fitbit API data schema validator."""

    def validate_recovery(self, data: Dict[str, Any]) -> bool:
        """Validate Fitbit recovery data."""
        # TODO: Implement based on Fitbit API schema
        return True

    def validate_sleep(self, data: Dict[str, Any]) -> bool:
        """Validate Fitbit sleep data."""
        # TODO: Implement based on Fitbit API schema
        return True

    def validate_workout(self, data: Dict[str, Any]) -> bool:
        """Validate Fitbit workout data."""
        # TODO: Implement based on Fitbit API schema
        return True
