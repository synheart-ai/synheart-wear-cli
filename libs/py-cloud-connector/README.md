# Synheart Cloud Connector

OAuth token management library for Synheart wearable vendor integrations (Whoop, Garmin, Fitbit).

## Features

- **VendorType**: Enum for supported wearable vendors
- **TokenStore**: DynamoDB-based token storage with KMS encryption
- **TokenSet**: Standardized OAuth token data structure

## Installation

```bash
pip install -e libs/py-cloud-connector
```

Or with development dependencies:

```bash
pip install -e "libs/py-cloud-connector[dev]"
```

## Usage

### VendorType

```python
from synheart_cloud_connector import VendorType

# Use vendor types
vendor = VendorType.WHOOP
print(vendor.value)  # "whoop"

# Check if vendor is valid
if VendorType.is_valid("garmin"):
    print("Valid vendor")

# List all vendors
vendors = VendorType.list_vendors()  # ['whoop', 'garmin', 'fitbit']
```

### TokenStore

```python
from synheart_cloud_connector import TokenStore, TokenSet, VendorType
from datetime import datetime, timedelta

# Initialize token store
store = TokenStore(
    table_name="my-tokens-table",
    kms_key_id="your-kms-key-id",  # Optional
    region_name="us-west-2"
)

# Save tokens
tokens = TokenSet(
    access_token="access_token_value",
    refresh_token="refresh_token_value",
    expires_at=datetime.now() + timedelta(hours=1),
    vendor_user_id="vendor_user_123",
    scopes=["read:recovery", "read:sleep"]
)

store.save_tokens(VendorType.WHOOP, "user_123", tokens)

# Get tokens
tokens = store.get_tokens(VendorType.WHOOP, "user_123")
if tokens and not tokens.is_expired():
    print(f"Access token: {tokens.access_token}")

# Revoke tokens
store.revoke_tokens(VendorType.WHOOP, "user_123")

# Scan tokens
active_tokens = store.scan_tokens(
    vendor=VendorType.WHOOP,
    status="active",
    limit=10
)
```

## DynamoDB Table Schema

```
Table Name: <your-table-name>
Partition Key: token_key (String) - format: "{vendor}:{user_id}"

Attributes:
- vendor (String): Vendor type (whoop, garmin, fitbit)
- user_id (String): User ID
- access_token (Binary): Encrypted access token
- refresh_token (Binary): Encrypted refresh token
- expires_at (Number): Unix timestamp
- vendor_user_id (String): Vendor's user ID (optional)
- scopes (List): List of scopes (optional)
- status (String): active, revoked, expired
- created_at (Number): Unix timestamp
- updated_at (Number): Unix timestamp
```

## Environment Variables

- `AWS_REGION`: AWS region (default: us-west-2)
- `DYNAMODB_TABLE`: DynamoDB table name
- `KMS_KEY_ID`: KMS key ID for encryption (optional)

## Requirements

- Python >= 3.9
- boto3 >= 1.26.0
