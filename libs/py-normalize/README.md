# Synheart Normalize

Data normalization library for wearable vendor data, converting vendor-specific formats into standardized Synheart formats.

## Features

- **DataNormalizer**: Converts vendor-specific data to standardized format
- **NormalizedData**: Common data structure for all vendors
- **DataType**: Enum for different data types (recovery, sleep, workout, etc.)
- **VendorSchema**: Validation for vendor-specific data formats

## Installation

```bash
pip install -e libs/py-normalize
```

Or with development dependencies:

```bash
pip install -e "libs/py-normalize[dev]"
```

## Usage

### Normalize Recovery Data

```python
from synheart_normalize import DataNormalizer

# WHOOP recovery data
whoop_data = {
    "id": "123",
    "user_id": "456",
    "created_at": "2025-11-25T10:00:00Z",
    "score": {
        "recovery_score": 75,
        "hrv_rmssd_milli": 45,
        "resting_heart_rate": 60
    }
}

normalized = DataNormalizer.normalize_recovery(
    vendor="whoop",
    vendor_user_id="456",
    raw_data=whoop_data
)

print(f"Recovery Score: {normalized.recovery_score}")
print(f"HRV: {normalized.hrv_rmssd}")
print(f"Resting HR: {normalized.resting_hr}")
```

### Normalize Sleep Data

```python
from synheart_normalize import DataNormalizer

# WHOOP sleep data
whoop_sleep = {
    "id": "789",
    "user_id": "456",
    "created_at": "2025-11-25T08:00:00Z",
    "score": {
        "sleep_efficiency": 92.5,
        "stage_summary": {
            "total_slow_wave_sleep_time_milli": 7200000,  # 2 hours
            "total_light_sleep_time_milli": 14400000,     # 4 hours
            "total_rem_sleep_time_milli": 5400000,        # 1.5 hours
            "total_awake_time_milli": 1800000             # 30 min
        }
    }
}

normalized = DataNormalizer.normalize_sleep(
    vendor="whoop",
    vendor_user_id="456",
    raw_data=whoop_sleep
)

print(f"Sleep Efficiency: {normalized.sleep_efficiency}%")
print(f"Sleep Stages: {normalized.sleep_stages}")
```

### Data Types

```python
from synheart_normalize import DataType

# Available data types
print(DataType.RECOVERY)      # "recovery"
print(DataType.SLEEP)         # "sleep"
print(DataType.WORKOUT)       # "workout"
print(DataType.CYCLE)         # "cycle"
print(DataType.HEART_RATE)    # "heart_rate"
print(DataType.HRV)           # "hrv"
```

### Validate Vendor Data

```python
from synheart_normalize import WhoopSchema, GarminSchema

# Validate WHOOP data
schema = WhoopSchema()
is_valid = schema.validate_recovery(whoop_data)
```

## NormalizedData Fields

```python
@dataclass
class NormalizedData:
    # Metadata
    vendor: str                          # Vendor name
    vendor_user_id: str                  # Vendor's user ID
    data_type: DataType                  # Type of data
    timestamp: datetime                  # Timestamp

    # Common fields (optional)
    recovery_score: Optional[float]      # Recovery/readiness score
    hrv_rmssd: Optional[float]          # HRV RMSSD (ms)
    resting_hr: Optional[int]           # Resting heart rate (bpm)
    sleep_duration_minutes: Optional[int]
    sleep_efficiency: Optional[float]
    sleep_stages: Optional[Dict[str, int]]  # Minutes per stage
    workout_duration_minutes: Optional[int]
    workout_type: Optional[str]
    calories_burned: Optional[float]
    avg_heart_rate: Optional[int]
    max_heart_rate: Optional[int]

    # Raw data preserved for reference
    raw_data: Optional[Dict[str, Any]]
```

## Supported Vendors

- **WHOOP**: Full implementation for recovery and sleep data
- **Garmin**: Placeholder (TODO: implement based on API schema)
- **Fitbit**: Placeholder (TODO: implement based on API schema)

## Requirements

- Python >= 3.9
