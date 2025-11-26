"""
Synheart Normalize Library

Provides data normalization utilities for wearable vendor data,
converting vendor-specific formats into standardized Synheart formats.
"""

from .normalizer import DataNormalizer, NormalizedData, DataType
from .vendor_schemas import VendorSchema, WhoopSchema, GarminSchema, FitbitSchema

__version__ = "0.1.0"

__all__ = [
    "DataNormalizer",
    "NormalizedData",
    "DataType",
    "VendorSchema",
    "WhoopSchema",
    "GarminSchema",
    "FitbitSchema",
]
