"""
OAuth token storage and management using DynamoDB with KMS encryption.
"""

import base64
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict

try:
    import boto3
    from botocore.exceptions import ClientError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

from .vendor_types import VendorType


@dataclass
class TokenSet:
    """OAuth token set for a vendor connection."""

    access_token: str
    refresh_token: str
    expires_at: datetime
    vendor_user_id: Optional[str] = None
    scopes: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        if self.expires_at:
            data['expires_at'] = self.expires_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TokenSet':
        """Create from dictionary."""
        if isinstance(data.get('expires_at'), str):
            data['expires_at'] = datetime.fromisoformat(data['expires_at'])
        return cls(**data)

    def is_expired(self) -> bool:
        """Check if the access token is expired."""
        return datetime.now(timezone.utc) >= self.expires_at


class TokenError(Exception):
    """Base exception for token operations."""
    pass


class TokenNotFoundError(TokenError):
    """Raised when tokens are not found."""
    pass


class TokenStore:
    """
    DynamoDB-based token storage with KMS encryption.

    Table schema:
    - Partition key: token_key (string) - format: "{vendor}:{user_id}"
    - Attributes:
        - vendor: string
        - user_id: string
        - access_token: binary (encrypted)
        - refresh_token: binary (encrypted)
        - expires_at: number (unix timestamp)
        - vendor_user_id: string (optional)
        - scopes: list of strings (optional)
        - status: string (active, revoked, expired)
        - created_at: number (unix timestamp)
        - updated_at: number (unix timestamp)
    """

    def __init__(
        self,
        table_name: str,
        kms_key_id: Optional[str] = None,
        region_name: str = "us-west-2"
    ):
        """
        Initialize TokenStore.

        Args:
            table_name: DynamoDB table name
            kms_key_id: Optional KMS key ID for encryption
            region_name: AWS region name

        Raises:
            ImportError: If boto3 is not installed
        """
        if not HAS_BOTO3:
            raise ImportError(
                "boto3 is required for TokenStore. "
                "Install it with: pip install boto3"
            )

        self.table_name = table_name
        self.kms_key_id = kms_key_id
        self.region_name = region_name

        # Initialize AWS clients
        self.dynamodb = boto3.resource('dynamodb', region_name=region_name)
        self.table = self.dynamodb.Table(table_name)

        if kms_key_id:
            self.kms = boto3.client('kms', region_name=region_name)
        else:
            self.kms = None

    def _get_token_key(self, vendor: VendorType, user_id: str) -> str:
        """Generate the DynamoDB partition key."""
        return f"{vendor.value}:{user_id}"

    def _encrypt(self, plaintext: str) -> bytes:
        """Encrypt data using KMS."""
        if not self.kms or not self.kms_key_id:
            # No encryption configured, return base64 encoded
            return base64.b64encode(plaintext.encode('utf-8'))

        try:
            response = self.kms.encrypt(
                KeyId=self.kms_key_id,
                Plaintext=plaintext.encode('utf-8')
            )
            return response['CiphertextBlob']
        except Exception as e:
            raise TokenError(f"Failed to encrypt token: {e}") from e

    def _decrypt(self, ciphertext: bytes) -> str:
        """Decrypt data using KMS."""
        if not self.kms or not self.kms_key_id:
            # No encryption configured, decode base64
            return base64.b64decode(ciphertext).decode('utf-8')

        try:
            response = self.kms.decrypt(
                CiphertextBlob=ciphertext
            )
            return response['Plaintext'].decode('utf-8')
        except Exception as e:
            raise TokenError(f"Failed to decrypt token: {e}") from e

    def save_tokens(
        self,
        vendor: VendorType,
        user_id: str,
        tokens: TokenSet,
        status: str = "active"
    ) -> None:
        """
        Save OAuth tokens to DynamoDB.

        Args:
            vendor: Vendor type
            user_id: User ID
            tokens: Token set to save
            status: Token status (active, revoked, expired)

        Raises:
            TokenError: If save operation fails
        """
        token_key = self._get_token_key(vendor, user_id)

        try:
            # Encrypt tokens
            access_token_enc = self._encrypt(tokens.access_token)
            refresh_token_enc = self._encrypt(tokens.refresh_token)

            # Prepare item
            now = int(datetime.now(timezone.utc).timestamp())
            item = {
                'token_key': token_key,
                'vendor': vendor.value,
                'user_id': user_id,
                'access_token': access_token_enc,
                'refresh_token': refresh_token_enc,
                'expires_at': int(tokens.expires_at.timestamp()),
                'status': status,
                'updated_at': now,
            }

            # Add optional fields
            if tokens.vendor_user_id:
                item['vendor_user_id'] = tokens.vendor_user_id
            if tokens.scopes:
                item['scopes'] = tokens.scopes

            # Check if item exists to set created_at
            try:
                response = self.table.get_item(Key={'token_key': token_key})
                if 'Item' in response:
                    item['created_at'] = response['Item'].get('created_at', now)
                else:
                    item['created_at'] = now
            except ClientError:
                item['created_at'] = now

            # Save to DynamoDB
            self.table.put_item(Item=item)

        except ClientError as e:
            raise TokenError(f"Failed to save tokens: {e}") from e

    def get_tokens(
        self,
        vendor: VendorType,
        user_id: str
    ) -> Optional[TokenSet]:
        """
        Retrieve OAuth tokens from DynamoDB.

        Args:
            vendor: Vendor type
            user_id: User ID

        Returns:
            TokenSet if found and active, None otherwise

        Raises:
            TokenError: If retrieval fails
        """
        token_key = self._get_token_key(vendor, user_id)

        try:
            response = self.table.get_item(Key={'token_key': token_key})

            if 'Item' not in response:
                return None

            item = response['Item']

            # Check status
            if item.get('status') != 'active':
                return None

            # Decrypt tokens
            access_token = self._decrypt(item['access_token'].value)
            refresh_token = self._decrypt(item['refresh_token'].value)

            # Parse expires_at
            expires_at = datetime.fromtimestamp(
                item['expires_at'],
                tz=timezone.utc
            )

            return TokenSet(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
                vendor_user_id=item.get('vendor_user_id'),
                scopes=item.get('scopes')
            )

        except ClientError as e:
            raise TokenError(f"Failed to get tokens: {e}") from e

    def revoke_tokens(
        self,
        vendor: VendorType,
        user_id: str
    ) -> None:
        """
        Revoke OAuth tokens (mark as revoked, don't delete).

        Args:
            vendor: Vendor type
            user_id: User ID

        Raises:
            TokenNotFoundError: If tokens don't exist
            TokenError: If revocation fails
        """
        token_key = self._get_token_key(vendor, user_id)

        try:
            # Update status to revoked
            now = int(datetime.now(timezone.utc).timestamp())

            response = self.table.update_item(
                Key={'token_key': token_key},
                UpdateExpression='SET #status = :status, updated_at = :updated_at',
                ExpressionAttributeNames={
                    '#status': 'status'
                },
                ExpressionAttributeValues={
                    ':status': 'revoked',
                    ':updated_at': now
                },
                ConditionExpression='attribute_exists(token_key)',
                ReturnValues='UPDATED_NEW'
            )

        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                raise TokenNotFoundError(
                    f"Tokens not found for {vendor.value}:{user_id}"
                ) from e
            raise TokenError(f"Failed to revoke tokens: {e}") from e

    def delete_tokens(
        self,
        vendor: VendorType,
        user_id: str
    ) -> None:
        """
        Permanently delete OAuth tokens.

        Args:
            vendor: Vendor type
            user_id: User ID

        Raises:
            TokenError: If deletion fails
        """
        token_key = self._get_token_key(vendor, user_id)

        try:
            self.table.delete_item(Key={'token_key': token_key})
        except ClientError as e:
            raise TokenError(f"Failed to delete tokens: {e}") from e

    def scan_tokens(
        self,
        vendor: Optional[VendorType] = None,
        status: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Scan tokens table with optional filters.

        Args:
            vendor: Filter by vendor type
            status: Filter by status
            limit: Maximum number of items to return

        Returns:
            List of token metadata (without decrypted tokens)

        Raises:
            TokenError: If scan fails
        """
        try:
            scan_kwargs = {}

            # Build filter expression
            filter_expressions = []
            expression_values = {}

            if vendor:
                filter_expressions.append('vendor = :vendor')
                expression_values[':vendor'] = vendor.value

            if status:
                filter_expressions.append('#status = :status')
                scan_kwargs['ExpressionAttributeNames'] = {'#status': 'status'}
                expression_values[':status'] = status

            if filter_expressions:
                scan_kwargs['FilterExpression'] = ' AND '.join(filter_expressions)
                scan_kwargs['ExpressionAttributeValues'] = expression_values

            if limit:
                scan_kwargs['Limit'] = limit

            # Perform scan
            response = self.table.scan(**scan_kwargs)

            items = []
            for item in response.get('Items', []):
                # Return metadata without decrypted tokens
                items.append({
                    'vendor': item['vendor'],
                    'user_id': item['user_id'],
                    'status': item.get('status'),
                    'expires_at': datetime.fromtimestamp(
                        item['expires_at'],
                        tz=timezone.utc
                    ).isoformat(),
                    'vendor_user_id': item.get('vendor_user_id'),
                    'scopes': item.get('scopes'),
                    'created_at': datetime.fromtimestamp(
                        item.get('created_at', 0),
                        tz=timezone.utc
                    ).isoformat() if item.get('created_at') else None,
                    'updated_at': datetime.fromtimestamp(
                        item.get('updated_at', 0),
                        tz=timezone.utc
                    ).isoformat() if item.get('updated_at') else None,
                })

            return items

        except ClientError as e:
            raise TokenError(f"Failed to scan tokens: {e}") from e
