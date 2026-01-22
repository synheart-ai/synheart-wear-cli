"""Unified FastAPI application for all cloud connector services."""

import os
from typing import Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse

from synheart_cloud_connector import CloudConnectorError
from synheart_cloud_connector.jobs import JobQueue
from synheart_cloud_connector.rate_limit import RateLimiter
from synheart_cloud_connector.tokens import TokenStore
from synheart_cloud_connector.vendor_types import RateLimitConfig, VendorType

# Import vendor connectors using importlib (directory names have hyphens)
import sys
import importlib.util
from pathlib import Path

# Import connectors from server directory
from server.whoop_connector import WhoopConnector

# TODO: Add Garmin connector when available
# from server.garmin_connector import GarminConnector
GarminConnector = None  # Placeholder for now

# Initialize FastAPI app
app = FastAPI(
    title="Synheart Wear Cloud Connector Service",
    description="Unified cloud integration service for all wearable vendors",
    version="1.0.0",
)

# Check if we're in dev mode (use mocked services)
DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"
LOCAL_MODE = os.getenv("LOCAL_MODE", "false").lower() == "true"
use_mocks = DEV_MODE or LOCAL_MODE

# Load shared configuration from environment
DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE", "cloud_connector_tokens")
KMS_KEY_ID = os.getenv("KMS_KEY_ID")

# Vendor-specific secrets
WHOOP_CLIENT_ID = os.getenv("WHOOP_CLIENT_ID", "")
WHOOP_CLIENT_SECRET = os.getenv("WHOOP_CLIENT_SECRET", "")
WHOOP_WEBHOOK_SECRET = os.getenv("WHOOP_WEBHOOK_SECRET", "")

GARMIN_CLIENT_ID = os.getenv("GARMIN_CLIENT_ID", "")
GARMIN_CLIENT_SECRET = os.getenv("GARMIN_CLIENT_SECRET", "")
GARMIN_WEBHOOK_SECRET = os.getenv("GARMIN_WEBHOOK_SECRET", "")

# Initialize shared dependencies
if use_mocks:
    # Use mocked services for local development
    # Mock token store for local testing
    class MockTokenStore:
        """Mock token store for local testing without AWS. Persists to disk."""

        def __init__(self, *args, **kwargs):
            import json
            from pathlib import Path

            self.tokens_file = Path(__file__).parent.parent.parent / "__dev__" / "tokens.json"
            self.tokens_file.parent.mkdir(parents=True, exist_ok=True)
            self.tokens = {}
            if self.tokens_file.exists():
                try:
                    with open(self.tokens_file, "r") as f:
                        data = json.load(f)
                        from synheart_cloud_connector.vendor_types import OAuthTokens
                        from datetime import datetime, timezone

                        for key, token_data in data.items():
                            if token_data.get("expires_at"):
                                if isinstance(token_data["expires_at"], str):
                                    dt = datetime.fromisoformat(
                                        token_data["expires_at"].replace("Z", "+00:00")
                                    )
                                    if dt.tzinfo is None:
                                        dt = dt.replace(tzinfo=timezone.utc)
                                    token_data["expires_at"] = dt
                            self.tokens[key] = OAuthTokens(**token_data)
                except Exception:
                    self.tokens = {}

        def save_tokens(self, vendor, user_id, tokens, vendor_meta=None):
            key = f"{vendor.value}:{user_id}"
            self.tokens[key] = tokens
            self._save_to_disk()
            from synheart_cloud_connector.vendor_types import TokenRecord, TokenStatus
            import datetime

            return TokenRecord(
                pk=key,
                sk=datetime.datetime.now().isoformat(),
                access_token="encrypted_token",
                refresh_token="encrypted_refresh",
                expires_at=int(datetime.datetime.now().timestamp()) + 3600,
                scopes=tokens.scopes,
                status=TokenStatus.ACTIVE,
            )

        def get_tokens(self, vendor, user_id):
            key = f"{vendor.value}:{user_id}"
            return self.tokens.get(key)

        def update_last_webhook(self, vendor, user_id):
            pass

        def update_last_pull(self, vendor, user_id):
            pass

        def revoke_tokens(self, vendor, user_id):
            key = f"{vendor.value}:{user_id}"
            if key in self.tokens:
                del self.tokens[key]
                self._save_to_disk()

        def _save_to_disk(self):
            import json
            from datetime import datetime
            from synheart_cloud_connector.vendor_types import OAuthTokens

            data = {}
            for key, tokens in self.tokens.items():
                token_dict = tokens.model_dump(mode="json")
                if token_dict.get("expires_at") and isinstance(token_dict["expires_at"], datetime):
                    token_dict["expires_at"] = token_dict["expires_at"].isoformat()
                data[key] = token_dict
            try:
                with open(self.tokens_file, "w") as f:
                    json.dump(data, f, indent=2)
            except Exception:
                pass

    # Mock job queue for local testing
    class MockJobQueue:
        """Mock job queue for local testing without AWS SQS."""

        def __init__(self, *args, **kwargs):
            self.messages = []

        def enqueue_event(self, event, delay_seconds=0):
            message_id = f"msg_{len(self.messages)}"
            self.messages.append({"id": message_id, "event": event, "delay": delay_seconds})
            print(
                f"✓ Enqueued event: {event.event_type} for {event.user_id} (msg_id: {message_id})"
            )
            return message_id

    token_store = MockTokenStore()
    whoop_queue = MockJobQueue()
    garmin_queue = MockJobQueue()
    print("✓ Using mocked AWS services (local dev mode)")
else:
    # Use real AWS services for production
    token_store = TokenStore(table_name=DYNAMODB_TABLE, kms_key_id=KMS_KEY_ID)
    whoop_queue = JobQueue(queue_url=os.getenv("WHOOP_SQS_QUEUE_URL"))
    garmin_queue = JobQueue(queue_url=os.getenv("GARMIN_SQS_QUEUE_URL"))

rate_limiter = RateLimiter()

# Configure rate limits for all vendors
rate_limiter.configure(
    RateLimitConfig(
        vendor=VendorType.WHOOP,
        max_requests=100,
        time_window=60,
        max_burst=120,
    )
)
rate_limiter.configure(
    RateLimitConfig(
        vendor=VendorType.GARMIN,
        max_requests=200,
        time_window=60,
        max_burst=250,
    )
)

from synheart_cloud_connector.vendor_types import VendorConfig

whoop_config = VendorConfig(
    vendor=VendorType.WHOOP,
    client_id=WHOOP_CLIENT_ID,
    client_secret=WHOOP_CLIENT_SECRET,
    webhook_secret=WHOOP_WEBHOOK_SECRET,
    base_url="https://api.prod.whoop.com",
    auth_url="https://api.prod.whoop.com/oauth/oauth2/auth",
    token_url="https://api.prod.whoop.com/oauth/oauth2/token",
    scopes=["read:recovery", "read:sleep", "read:workout", "read:cycles", "read:profile"],
)

garmin_config = VendorConfig(
    vendor=VendorType.GARMIN,
    client_id=GARMIN_CLIENT_ID,
    client_secret=GARMIN_CLIENT_SECRET,
    webhook_secret=GARMIN_WEBHOOK_SECRET,
    base_url="https://api.garmin.com/wellness-api/rest",
    auth_url="https://connect.garmin.com/oauthConfirm",
    token_url="https://connectapi.garmin.com/oauth-service/oauth/exchange/user/2.0",
    scopes=["wellness"],
)

whoop = WhoopConnector(
    config=whoop_config,
    token_store=token_store,
    queue=whoop_queue,
    rate_limiter=rate_limiter,
)

# TODO: Initialize Garmin connector when available
# garmin = GarminConnector(
#     config=garmin_config,
#     token_store=token_store,
#     queue=garmin_queue,
#     rate_limiter=rate_limiter,
# )
garmin = None  # Placeholder for now

# Create vendor-specific routers with prefixes
v1_whoop_router = APIRouter(prefix="/v1/whoop-cloud", tags=["whoop"])
v1_garmin_router = APIRouter(prefix="/v1/garmin-cloud", tags=["garmin"])

# ============================================================================
# Health Check (unversioned)
# ============================================================================


@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check endpoint for monitoring."""
    checks = {}
    try:
        checks["dynamodb"] = "ok"
    except Exception:
        checks["dynamodb"] = "error"

    try:
        checks["sqs_whoop"] = "ok" if whoop_queue else "error"
        checks["sqs_garmin"] = "ok" if garmin_queue else "error"
    except Exception:
        checks["sqs_whoop"] = "error"
        checks["sqs_garmin"] = "error"

    try:
        checks["kms"] = "ok" if KMS_KEY_ID else "error"
    except Exception:
        checks["kms"] = "error"

    return {
        "status": "healthy",
        "version": "1.0.0",
        "service": "synheart-wear-cli",
        "vendors": ["whoop", "garmin"],
        "checks": checks,
    }


# ============================================================================
# WHOOP Routes
# ============================================================================


@v1_whoop_router.get("/oauth/authorize")
async def whoop_authorize(redirect_uri: str, state: str | None = None) -> dict[str, str]:
    """WHOOP OAuth authorization URL endpoint."""
    from fastapi import Query

    auth_url = whoop.build_authorization_url(redirect_uri=redirect_uri, state=state)
    return {"authorization_url": auth_url}


@v1_whoop_router.get("/oauth/callback")
async def whoop_oauth_callback_get(
    code: str,
    state: str,
    vendor: str = "whoop",
) -> dict[str, Any]:
    """WHOOP OAuth callback endpoint (GET)."""
    from fastapi import HTTPException, Query

    # Extract user_id from state (format: user_id:timestamp:nonce)
    try:
        user_id = state.split(":")[0]
    except (IndexError, AttributeError):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_state",
                "message": "Invalid state parameter format",
                "vendor": vendor,
            },
        )

    try:
        redirect_uri = os.getenv("WHOOP_REDIRECT_URI", "")
        tokens = await whoop.exchange_code(
            user_id=user_id,
            code=code,
            redirect_uri=redirect_uri,
        )
        return {
            "status": "connected",
            "vendor": vendor,
            "user_id": user_id,
            "scopes": tokens.scopes,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "exchange_failed",
                "message": str(e),
                "vendor": vendor,
            },
        )


@v1_whoop_router.post("/oauth/callback")
async def whoop_oauth_callback_post(request: Request) -> dict[str, Any]:
    """WHOOP OAuth callback endpoint (POST for mobile deep links)."""
    from fastapi import HTTPException

    body = await request.json()
    code = body.get("code")
    state = body.get("state")
    redirect_uri = body.get("redirect_uri", os.getenv("WHOOP_REDIRECT_URI", ""))
    vendor = body.get("vendor", "whoop")

    try:
        user_id = state.split(":")[0]
    except (IndexError, AttributeError):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_state",
                "message": "Invalid state parameter format",
                "vendor": vendor,
            },
        )

    try:
        tokens = await whoop.exchange_code(
            user_id=user_id,
            code=code,
            redirect_uri=redirect_uri,
        )
        return {
            "status": "connected",
            "vendor": vendor,
            "user_id": user_id,
            "scopes": tokens.scopes,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "exchange_failed",
                "message": str(e),
                "vendor": vendor,
            },
        )


@v1_whoop_router.post("/webhooks/whoop")
async def whoop_webhook_handler(request: Request) -> JSONResponse:
    """WHOOP webhook handler."""
    from fastapi import HTTPException

    headers = dict(request.headers)
    raw_body = await request.body()

    try:
        event_id = await whoop.process_webhook(headers, raw_body)
        return JSONResponse(
            content={
                "status": "received",
                "vendor": "whoop",
                "event_id": event_id,
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "webhook_error",
                "message": str(e),
                "vendor": "whoop",
            },
        )


@v1_whoop_router.delete("/oauth/disconnect")
async def whoop_disconnect(
    user_id: str,
    vendor: str = "whoop",
) -> dict[str, Any]:
    """WHOOP disconnect endpoint."""
    from fastapi import HTTPException, Query

    try:
        success = await whoop.revoke_tokens(user_id)
        if not success:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "not_found",
                    "message": "User-vendor binding not found",
                    "vendor": vendor,
                    "user_id": user_id,
                },
            )
        return {
            "status": "disconnected",
            "vendor": vendor,
            "user_id": user_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "server_error",
                "message": str(e),
                "vendor": vendor,
            },
        )


# ============================================================================
# Garmin Routes
# ============================================================================


@v1_garmin_router.get("/oauth/authorize")
async def garmin_authorize(redirect_uri: str, state: str | None = None) -> dict[str, str]:
    """Garmin OAuth authorization URL endpoint."""
    auth_url = garmin.build_authorization_url(redirect_uri=redirect_uri, state=state)
    return {"authorization_url": auth_url}


@v1_garmin_router.get("/oauth/callback")
async def garmin_oauth_callback_get(
    code: str,
    state: str,
    vendor: str = "garmin",
) -> dict[str, Any]:
    """Garmin OAuth callback endpoint (GET)."""
    from fastapi import HTTPException, Query

    try:
        user_id = state.split(":")[0]
    except (IndexError, AttributeError):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_state",
                "message": "Invalid state parameter format",
                "vendor": vendor,
            },
        )

    try:
        redirect_uri = os.getenv("GARMIN_REDIRECT_URI", "")
        tokens = await garmin.exchange_code(
            user_id=user_id,
            code=code,
            redirect_uri=redirect_uri,
        )
        return {
            "status": "connected",
            "vendor": vendor,
            "user_id": user_id,
            "scopes": tokens.scopes,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "exchange_failed",
                "message": str(e),
                "vendor": vendor,
            },
        )


@v1_garmin_router.post("/oauth/callback")
async def garmin_oauth_callback_post(request: Request) -> dict[str, Any]:
    """Garmin OAuth callback endpoint (POST for mobile deep links)."""
    from fastapi import HTTPException

    body = await request.json()
    code = body.get("code")
    state = body.get("state")
    redirect_uri = body.get("redirect_uri", os.getenv("GARMIN_REDIRECT_URI", ""))
    vendor = body.get("vendor", "garmin")

    try:
        user_id = state.split(":")[0]
    except (IndexError, AttributeError):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_state",
                "message": "Invalid state parameter format",
                "vendor": vendor,
            },
        )

    try:
        tokens = await garmin.exchange_code(
            user_id=user_id,
            code=code,
            redirect_uri=redirect_uri,
        )
        return {
            "status": "connected",
            "vendor": vendor,
            "user_id": user_id,
            "scopes": tokens.scopes,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "exchange_failed",
                "message": str(e),
                "vendor": vendor,
            },
        )


@v1_garmin_router.post("/webhooks/garmin")
async def garmin_webhook_handler(request: Request) -> JSONResponse:
    """Garmin webhook handler."""
    from fastapi import HTTPException

    headers = dict(request.headers)
    raw_body = await request.body()

    try:
        event_id = await garmin.process_webhook(headers, raw_body)
        return JSONResponse(
            content={
                "status": "received",
                "vendor": "garmin",
                "event_id": event_id,
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "webhook_error",
                "message": str(e),
                "vendor": "garmin",
            },
        )


@v1_garmin_router.delete("/oauth/disconnect")
async def garmin_disconnect(
    user_id: str,
    vendor: str = "garmin",
) -> dict[str, Any]:
    """Garmin disconnect endpoint."""
    from fastapi import HTTPException, Query

    try:
        success = await garmin.revoke_tokens(user_id)
        if not success:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "not_found",
                    "message": "User-vendor binding not found",
                    "vendor": vendor,
                    "user_id": user_id,
                },
            )
        return {
            "status": "disconnected",
            "vendor": vendor,
            "user_id": user_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "server_error",
                "message": str(e),
                "vendor": vendor,
            },
        )


# Include routers
app.include_router(v1_whoop_router)
app.include_router(v1_garmin_router)


# ============================================================================
# Data Endpoints (with Flux HSI processing)
# ============================================================================

# Import Flux integration
from server.flux_integration import (
    is_flux_enabled,
    process_whoop_to_hsi,
    process_garmin_to_hsi,
    whoop_to_raw_events_ndjson,
    garmin_to_raw_events_ndjson,
)

# Data router for fetching and processing wearable data
v1_data_router = APIRouter(prefix="/v1/data", tags=["data"])


@v1_data_router.get("/{user_id}/recovery")
async def get_recovery_data(
    user_id: str,
    limit: int = 25,
    since: str | None = None,
) -> dict[str, Any]:
    """Get recovery data for a user."""
    from fastapi import HTTPException

    try:
        # Fetch data from WHOOP (currently only vendor with full support)
        data = await whoop.fetch_recovery(user_id, limit=limit, since=since)
        return {"records": data, "count": len(data), "user_id": user_id}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"code": "fetch_error", "message": str(e)},
        )


@v1_data_router.get("/{user_id}/sleep")
async def get_sleep_data(
    user_id: str,
    limit: int = 25,
    since: str | None = None,
) -> dict[str, Any]:
    """Get sleep data for a user."""
    from fastapi import HTTPException

    try:
        data = await whoop.fetch_sleep(user_id, limit=limit, since=since)
        return {"records": data, "count": len(data), "user_id": user_id}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"code": "fetch_error", "message": str(e)},
        )


@v1_data_router.get("/{user_id}/workout")
async def get_workout_data(
    user_id: str,
    limit: int = 25,
    since: str | None = None,
) -> dict[str, Any]:
    """Get workout data for a user."""
    from fastapi import HTTPException

    try:
        data = await whoop.fetch_workout(user_id, limit=limit, since=since)
        return {"records": data, "count": len(data), "user_id": user_id}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"code": "fetch_error", "message": str(e)},
        )


@v1_data_router.get("/{user_id}/cycle")
async def get_cycle_data(
    user_id: str,
    limit: int = 25,
    since: str | None = None,
) -> dict[str, Any]:
    """Get cycle (daily strain) data for a user."""
    from fastapi import HTTPException

    try:
        data = await whoop.fetch_cycle(user_id, limit=limit, since=since)
        return {"records": data, "count": len(data), "user_id": user_id}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"code": "fetch_error", "message": str(e)},
        )


@v1_data_router.get("/{user_id}/profile")
async def get_user_profile(user_id: str) -> dict[str, Any]:
    """Get user profile."""
    from fastapi import HTTPException

    try:
        profile = await whoop.fetch_profile(user_id)
        return profile
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"code": "fetch_error", "message": str(e)},
        )


@v1_data_router.post("/{user_id}/pull")
async def pull_all_data(
    user_id: str,
    limit: int = 25,
    since: str | None = None,
    resource_types: list[str] | None = None,
) -> dict[str, Any]:
    """
    Pull all data types for a user.

    Args:
        user_id: User identifier
        limit: Max records per resource type
        since: ISO8601 timestamp to fetch data from
        resource_types: List of types to fetch (default: all)

    Returns:
        Dict with results for each resource type
    """
    from fastapi import HTTPException

    if resource_types is None:
        resource_types = ["recovery", "sleep", "workout", "cycle"]

    results: dict[str, Any] = {}
    total_records = 0

    for resource_type in resource_types:
        try:
            if resource_type == "recovery":
                data = await whoop.fetch_recovery(user_id, limit=limit, since=since)
            elif resource_type == "sleep":
                data = await whoop.fetch_sleep(user_id, limit=limit, since=since)
            elif resource_type == "workout":
                data = await whoop.fetch_workout(user_id, limit=limit, since=since)
            elif resource_type == "cycle":
                data = await whoop.fetch_cycle(user_id, limit=limit, since=since)
            else:
                results[resource_type] = {"error": f"Unknown resource type: {resource_type}"}
                continue

            results[resource_type] = {"records": len(data), "data": data}
            total_records += len(data)
        except Exception as e:
            results[resource_type] = {"error": str(e), "records": 0}

    return {
        "user_id": user_id,
        "pull_type": "manual",
        "since": since,
        "total_records": total_records,
        "results": results,
    }


@v1_data_router.get("/{user_id}/export/raw")
async def export_raw_events(
    user_id: str,
    vendor: str = "whoop",
    limit: int = 25,
    since: str | None = None,
    device_id: str | None = None,
    timezone: str = "UTC",
) -> Any:
    """
    Export data as wear.raw_event.v1 NDJSON format.

    This format is compatible with the Flux CLI for HSI processing.

    Args:
        user_id: User identifier
        vendor: Vendor (whoop, garmin)
        limit: Max records per resource type
        since: ISO8601 timestamp
        device_id: Device identifier for provenance
        timezone: User timezone (IANA format)

    Returns:
        NDJSON string with wear.raw_event.v1 records
    """
    from fastapi import HTTPException
    from fastapi.responses import PlainTextResponse

    if device_id is None:
        device_id = f"{vendor}-{user_id}"

    try:
        if vendor == "whoop":
            # Fetch all data types
            recovery = await whoop.fetch_recovery(user_id, limit=limit, since=since)
            sleep = await whoop.fetch_sleep(user_id, limit=limit, since=since)
            workout = await whoop.fetch_workout(user_id, limit=limit, since=since)
            cycle = await whoop.fetch_cycle(user_id, limit=limit, since=since)

            whoop_data = {
                "recovery": recovery,
                "sleep": sleep,
                "workout": workout,
                "cycle": cycle,
            }

            ndjson = whoop_to_raw_events_ndjson(whoop_data, device_id, timezone)
        elif vendor == "garmin":
            # TODO: Implement Garmin data fetching
            raise HTTPException(
                status_code=501,
                detail={"code": "not_implemented", "message": "Garmin export not yet implemented"},
            )
        else:
            raise HTTPException(
                status_code=400,
                detail={"code": "invalid_vendor", "message": f"Unknown vendor: {vendor}"},
            )

        return PlainTextResponse(
            content=ndjson,
            media_type="application/x-ndjson",
            headers={"Content-Disposition": f"attachment; filename=raw_events_{user_id}.ndjson"},
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"code": "export_error", "message": str(e)},
        )


@v1_data_router.get("/{user_id}/hsi")
async def get_hsi_data(
    user_id: str,
    vendor: str = "whoop",
    limit: int = 25,
    since: str | None = None,
    device_id: str | None = None,
    timezone: str = "UTC",
    baseline_days: int = 14,
) -> dict[str, Any]:
    """
    Get HSI-processed data using Flux.

    Requires USE_FLUX=true and Flux binary to be available.

    Args:
        user_id: User identifier
        vendor: Vendor (whoop, garmin)
        limit: Max records per resource type
        since: ISO8601 timestamp
        device_id: Device identifier
        timezone: User timezone (IANA format)
        baseline_days: Baseline window for normalization

    Returns:
        HSI-compliant JSON payloads
    """
    from fastapi import HTTPException

    if not is_flux_enabled():
        raise HTTPException(
            status_code=503,
            detail={
                "code": "flux_disabled",
                "message": "Flux processing is not enabled. Set USE_FLUX=true and ensure Flux binary is available.",
            },
        )

    if device_id is None:
        device_id = f"{vendor}-{user_id}"

    try:
        if vendor == "whoop":
            # Fetch all data types
            recovery = await whoop.fetch_recovery(user_id, limit=limit, since=since)
            sleep = await whoop.fetch_sleep(user_id, limit=limit, since=since)
            workout = await whoop.fetch_workout(user_id, limit=limit, since=since)
            cycle = await whoop.fetch_cycle(user_id, limit=limit, since=since)

            whoop_data = {
                "recovery": recovery,
                "sleep": sleep,
                "workout": workout,
                "cycle": cycle,
            }

            hsi_payloads = process_whoop_to_hsi(
                whoop_data,
                user_timezone=timezone,
                device_id=device_id,
                baseline_days=baseline_days,
            )
        elif vendor == "garmin":
            raise HTTPException(
                status_code=501,
                detail={"code": "not_implemented", "message": "Garmin HSI processing not yet implemented"},
            )
        else:
            raise HTTPException(
                status_code=400,
                detail={"code": "invalid_vendor", "message": f"Unknown vendor: {vendor}"},
            )

        return {
            "user_id": user_id,
            "vendor": vendor,
            "hsi_payloads": hsi_payloads,
            "count": len(hsi_payloads),
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=500,
            detail={"code": "flux_error", "message": str(e)},
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"code": "processing_error", "message": str(e)},
        )


# Include data router
app.include_router(v1_data_router)


# Error handler
@app.exception_handler(CloudConnectorError)
async def cloud_connector_error_handler(request: Request, exc: CloudConnectorError) -> JSONResponse:
    """Handle CloudConnectorError exceptions."""
    return JSONResponse(
        status_code=500,
        content=exc.to_dict(),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
