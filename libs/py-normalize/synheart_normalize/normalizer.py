"""
Core data normalization functionality.
"""

from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum


class DataType(str, Enum):
    """Types of wearable data."""
    RECOVERY = "recovery"
    SLEEP = "sleep"
    WORKOUT = "workout"
    CYCLE = "cycle"
    HEART_RATE = "heart_rate"
    HRV = "hrv"


@dataclass
class NormalizedData:
    """Standardized wearable data format."""

    # Metadata
    vendor: str
    vendor_user_id: str
    data_type: DataType
    timestamp: datetime

    # Common fields (optional based on data type)
    recovery_score: Optional[float] = None
    hrv_rmssd: Optional[float] = None
    resting_hr: Optional[int] = None
    sleep_duration_minutes: Optional[int] = None
    sleep_efficiency: Optional[float] = None
    sleep_stages: Optional[Dict[str, int]] = None  # deep, light, rem, awake
    workout_duration_minutes: Optional[int] = None
    workout_type: Optional[str] = None
    calories_burned: Optional[float] = None
    avg_heart_rate: Optional[int] = None
    max_heart_rate: Optional[int] = None

    # Raw vendor data (preserved for reference)
    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        if self.timestamp:
            data['timestamp'] = self.timestamp.isoformat()
        if self.data_type:
            data['data_type'] = self.data_type.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NormalizedData':
        """Create from dictionary."""
        if isinstance(data.get('timestamp'), str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        if isinstance(data.get('data_type'), str):
            data['data_type'] = DataType(data['data_type'])
        return cls(**data)


class DataNormalizer:
    """Normalizes vendor-specific data into standardized format."""

    @staticmethod
    def normalize_recovery(
        vendor: str,
        vendor_user_id: str,
        raw_data: Dict[str, Any]
    ) -> NormalizedData:
        """
        Normalize recovery/readiness data.

        Args:
            vendor: Vendor name (whoop, garmin, fitbit)
            vendor_user_id: Vendor's user ID
            raw_data: Raw vendor data

        Returns:
            NormalizedData instance
        """
        vendor_lower = vendor.lower()

        if vendor_lower == "whoop":
            return DataNormalizer._normalize_whoop_recovery(vendor_user_id, raw_data)
        elif vendor_lower == "garmin":
            return DataNormalizer._normalize_garmin_recovery(vendor_user_id, raw_data)
        elif vendor_lower == "fitbit":
            return DataNormalizer._normalize_fitbit_recovery(vendor_user_id, raw_data)
        else:
            raise ValueError(f"Unsupported vendor: {vendor}")

    @staticmethod
    def normalize_sleep(
        vendor: str,
        vendor_user_id: str,
        raw_data: Dict[str, Any]
    ) -> NormalizedData:
        """
        Normalize sleep data.

        Args:
            vendor: Vendor name (whoop, garmin, fitbit)
            vendor_user_id: Vendor's user ID
            raw_data: Raw vendor data

        Returns:
            NormalizedData instance
        """
        vendor_lower = vendor.lower()

        if vendor_lower == "whoop":
            return DataNormalizer._normalize_whoop_sleep(vendor_user_id, raw_data)
        elif vendor_lower == "garmin":
            return DataNormalizer._normalize_garmin_sleep(vendor_user_id, raw_data)
        elif vendor_lower == "fitbit":
            return DataNormalizer._normalize_fitbit_sleep(vendor_user_id, raw_data)
        else:
            raise ValueError(f"Unsupported vendor: {vendor}")

    # WHOOP normalizers
    @staticmethod
    def _normalize_whoop_recovery(
        vendor_user_id: str,
        raw_data: Dict[str, Any]
    ) -> NormalizedData:
        """Normalize WHOOP recovery data."""
        score = raw_data.get('score', {})

        return NormalizedData(
            vendor="whoop",
            vendor_user_id=vendor_user_id,
            data_type=DataType.RECOVERY,
            timestamp=datetime.fromisoformat(raw_data.get('created_at')),
            recovery_score=score.get('recovery_score'),
            hrv_rmssd=score.get('hrv_rmssd_milli'),
            resting_hr=score.get('resting_heart_rate'),
            raw_data=raw_data
        )

    @staticmethod
    def _normalize_whoop_sleep(
        vendor_user_id: str,
        raw_data: Dict[str, Any]
    ) -> NormalizedData:
        """Normalize WHOOP sleep data."""
        score = raw_data.get('score', {})
        sleep_performance = score.get('stage_summary', {})

        sleep_stages = {
            'deep': sleep_performance.get('total_slow_wave_sleep_time_milli', 0) // 60000,
            'light': sleep_performance.get('total_light_sleep_time_milli', 0) // 60000,
            'rem': sleep_performance.get('total_rem_sleep_time_milli', 0) // 60000,
            'awake': sleep_performance.get('total_awake_time_milli', 0) // 60000,
        }

        return NormalizedData(
            vendor="whoop",
            vendor_user_id=vendor_user_id,
            data_type=DataType.SLEEP,
            timestamp=datetime.fromisoformat(raw_data.get('created_at')),
            sleep_duration_minutes=raw_data.get('score', {}).get('sleep_needed', {}).get('baseline_milli', 0) // 60000,
            sleep_efficiency=score.get('sleep_efficiency'),
            sleep_stages=sleep_stages,
            raw_data=raw_data
        )

    # Garmin normalizers (placeholder - implement based on Garmin API schema)
    @staticmethod
    def _normalize_garmin_recovery(
        vendor_user_id: str,
        raw_data: Dict[str, Any]
    ) -> NormalizedData:
        """Normalize Garmin recovery/body battery data."""
        # TODO: Implement based on Garmin API schema
        return NormalizedData(
            vendor="garmin",
            vendor_user_id=vendor_user_id,
            data_type=DataType.RECOVERY,
            timestamp=datetime.now(),
            raw_data=raw_data
        )

    @staticmethod
    def _normalize_garmin_sleep(
        vendor_user_id: str,
        raw_data: Dict[str, Any]
    ) -> NormalizedData:
        """Normalize Garmin sleep data."""
        # TODO: Implement based on Garmin API schema
        return NormalizedData(
            vendor="garmin",
            vendor_user_id=vendor_user_id,
            data_type=DataType.SLEEP,
            timestamp=datetime.now(),
            raw_data=raw_data
        )

    # Fitbit normalizers (placeholder - implement based on Fitbit API schema)
    @staticmethod
    def _normalize_fitbit_recovery(
        vendor_user_id: str,
        raw_data: Dict[str, Any]
    ) -> NormalizedData:
        """Normalize Fitbit readiness data."""
        # TODO: Implement based on Fitbit API schema
        return NormalizedData(
            vendor="fitbit",
            vendor_user_id=vendor_user_id,
            data_type=DataType.RECOVERY,
            timestamp=datetime.now(),
            raw_data=raw_data
        )

    @staticmethod
    def _normalize_fitbit_sleep(
        vendor_user_id: str,
        raw_data: Dict[str, Any]
    ) -> NormalizedData:
        """Normalize Fitbit sleep data."""
        # TODO: Implement based on Fitbit API schema
        return NormalizedData(
            vendor="fitbit",
            vendor_user_id=vendor_user_id,
            data_type=DataType.SLEEP,
            timestamp=datetime.now(),
            raw_data=raw_data
        )
