# Synheart Wear CLI (`wear`)

[![PyPI version](https://badge.fury.io/py/synheart-wear-cli.svg)](https://pypi.org/project/synheart-wear-cli)
[![Python Versions](https://img.shields.io/pypi/pyversions/synheart-wear-cli.svg)](https://pypi.org/project/synheart-wear-cli)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Downloads](https://pepy.tech/badge/synheart-wear-cli)](https://pepy.tech/project/synheart-wear-cli)

**All-in-one local development tool for cloud wearable integrations** — Complete CLI + FastAPI server + ngrok integration for WHOOP, Garmin, and Fitbit testing.



## 🚀 What is This?

The Synheart Wear CLI combines a **command-line interface** with an **embedded FastAPI server** for local wearable development:

### CLI Features:
- 🔧 Manage OAuth tokens (list, refresh, revoke)
- 📥 Pull data from cloud APIs
- 🔍 Inspect webhook events
- 🚀 Start/stop local dev server

### Server Features:
- 🔐 OAuth flows for cloud wearables (WHOOP, Fitbit, Garmin*)
- 🪝 Webhook endpoints for real-time data
- 🌐 Automatic ngrok tunnel exposure
- 💾 Local token storage (dev mode) or DynamoDB + KMS (production)
- 📊 Data normalization to Synheart format

**Perfect for:**
- Testing SDK integrations locally
- Developing apps with WHOOP/Garmin data
- Prototyping cloud wearable features
- Full OAuth flow testing

_* Garmin support in development_

## 📋 Prerequisites

- **Python 3.11+**
- **ngrok account** (free): https://ngrok.com/
- **Wearable API credentials** (WHOOP, Garmin, etc.)
- **AWS Account** (optional for production token storage)

## 🚀 Quick Start

### 1. Install

**Option A: Install from PyPI (Recommended)**

```bash
# Install the CLI globally
pip install synheart-wear-cli

# Verify installation
wear version
wear --help
```

**Option B: Install from Source**

```bash
# Clone the repository
git clone https://github.com/synheart-ai/synheart-wear-cli.git
cd synheart-wear-cli

# Install in development mode
pip install -e ".[dev]"

# Verify installation
python3 wear.py --help
# Or if installed globally:
wear --help
```

**Note:** All required libraries are automatically installed. No separate cloning needed.

### 2. Configure ngrok

```bash
# Get your auth token from https://dashboard.ngrok.com/get-started/your-authtoken
ngrok config add-authtoken YOUR_TOKEN
```

### 3. Create Environment File

Create `.env.local` in the CLI directory:

```bash
# WHOOP Credentials
WHOOP_CLIENT_ID=your_whoop_client_id
WHOOP_CLIENT_SECRET=your_whoop_client_secret

# AWS (optional - for production token storage)
AWS_REGION=us-east-1
DYNAMODB_TABLE=synheart-wear-tokens
KMS_KEY_ID=alias/synheart-wear

# Development Mode (automatically enabled by CLI)
DEV_MODE=true
WEBHOOK_RECORD=true
```

### 4. Start Development Server

```bash
# Start WHOOP connector with ngrok
python3 wear.py start dev --vendor whoop --port 8000

# Or with auto-open browser for OAuth:
python3 wear.py start dev --vendor whoop --open-browser

# The CLI will automatically:
# ✅ Start local FastAPI server
# ✅ Start ngrok tunnel
# ✅ Display ngrok URL for SDK configuration
# ✅ Enable webhook recording
# ✅ Setup hot-reload for code changes
```

**Output:**
```
🚀 Starting Synheart Wear
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📍 Configuration:
   Mode:           dev
   Vendor:         whoop
   Port:           8000
   Auto-reload:    ✅ enabled
   Webhook record: ✅ enabled

📝 Auto-loaded environment from: .env.local

🌐 Endpoints:
   API Docs:      http://localhost:8000/docs
   Health Check:  http://localhost:8000/health
   OAuth Auth:    http://localhost:8000/v1/oauth/authorize
   Webhooks:      http://localhost:8000/v1/webhooks/whoop

🌐 Starting ngrok tunnel...
✅ ngrok tunnel started: https://abc123-xyz.ngrok-free.app

📱 SDK Configuration:
   Use this URL in your Flutter app:
   baseUrl: 'https://abc123-xyz.ngrok-free.app'
```

## 📖 Commands

### `wear start dev` - Start Local Development Server

Start local server with automatic ngrok tunneling.

```bash
# Start WHOOP connector
python3 wear.py start dev --vendor whoop --port 8000

# Start with auto-open browser for OAuth
python3 wear.py start dev --vendor whoop --open-browser

# Start unified service (all vendors - Garmin coming soon)
python3 wear.py start dev --port 8000

# Use specific environment file
python3 wear.py start dev --vendor whoop --env .env.production

# Disable auto-reload
python3 wear.py start dev --vendor whoop --no-reload

# Verbose logging
python3 wear.py start dev --vendor whoop --verbose
```

**Options:**
- `--vendor, -v` - Vendor to run (`whoop`, `garmin`, or omit for all)
- `--port, -p` - Port to run on (default: 8000)
- `--reload/--no-reload` - Auto-reload on code changes (default: enabled)
- `--env` - Environment file to load (`.env.local`, `.env.production`)
- `--open-browser` - Automatically open OAuth authorization URL
- `--webhook-record/--no-webhook-record` - Enable webhook recording (default: enabled)
- `--verbose` - Enable verbose logging

**What it does:**
- ✅ Starts FastAPI server on specified port
- ✅ Automatically starts ngrok tunnel
- ✅ Displays ngrok URL for SDK configuration
- ✅ Enables auto-reload for code changes
- ✅ Records webhooks to `__dev__/webhooks_recent.jsonl`

### `wear pull once` - Fetch Data from Cloud API

Pull data from vendor cloud API (requires OAuth connection first).

```bash
# Pull WHOOP recovery data (last 7 days)
python3 wear.py pull once --vendor whoop --since 7d

# Pull specific data types
python3 wear.py pull once --vendor whoop --since 30d --data-types recovery,sleep,workouts

# Pull from specific user
python3 wear.py pull once --vendor whoop --user-id abc123 --since 14d
```

**Options:**
- `--vendor` - Vendor to pull from (required)
- `--since` - Time range (e.g., `7d`, `30d`, `2h`)
- `--data-types` - Comma-separated data types (recovery, sleep, workouts, cycles)
- `--user-id` - Specific user ID (optional)

### `wear tokens` - Manage OAuth Tokens

List, refresh, or revoke OAuth tokens.

```bash
# List all tokens
python3 wear.py tokens list

# List tokens for specific vendor
python3 wear.py tokens list --vendor whoop

# Refresh expired token
python3 wear.py tokens refresh --vendor whoop --user-id abc123

# Revoke token (disconnect user)
python3 wear.py tokens revoke --vendor whoop --user-id abc123
```

### `wear webhook` - Webhook Management

Inspect webhook events recorded during development.

```bash
# Inspect recent webhooks (last 50)
python3 wear.py webhook inspect --limit 50

# Filter by vendor
python3 wear.py webhook inspect --vendor whoop --limit 100

# Show webhook details
python3 wear.py webhook inspect --verbose
```

## 🏗️ Architecture

```
synheart-wear-cli/
├── wear.py                  # Main CLI entry point
├── server/                  # Local development server
│   ├── whoop_api.py        # WHOOP OAuth + data endpoints
│   ├── garmin_api.py       # Garmin OAuth + data endpoints
│   ├── unified_api.py      # Unified service (all vendors)
│   └── whoop_connector.py  # WHOOP connector logic
├── libs/
│   ├── py-cloud-connector/ # OAuth token management
│   └── py-normalize/       # Data normalization
└── __dev__/                # Development data (auto-generated)
    ├── webhooks_recent.jsonl
    └── tokens.json
```

## 🔧 Development Workflow

### 1. Start Local Server

```bash
python3 wear.py start dev --vendor whoop --open-browser
```

### 2. Complete OAuth Flow

The browser will open automatically. Log in and authorize.

### 3. Configure SDK

Use the ngrok URL displayed in the terminal in your app:

**Flutter:**
```dart
final whoopProvider = WhoopProvider(
  baseUrl: 'https://abc123-xyz.ngrok-free.app',
  redirectUri: 'synheart://oauth/callback',
);
```

**Swift:**
```swift
let whoopProvider = WhoopProvider(
    baseUrl: URL(string: "https://abc123-xyz.ngrok-free.app")!,
    redirectUri: "synheart://oauth/callback"
)
```

**Kotlin:**
```kotlin
val whoopProvider = WhoopProvider(
    baseUrl = "https://abc123-xyz.ngrok-free.app",
    redirectUri = "synheart://oauth/callback"
)
```

### 4. Fetch Data

Once connected, fetch data from your app or use the CLI:

```bash
python3 wear.py pull once --vendor whoop --since 7d
```

### 5. Test Webhooks

Webhooks are automatically recorded to `__dev__/webhooks_recent.jsonl`:

```bash
python3 wear.py webhook inspect --limit 10
```

## 📡 API Endpoints

The local server exposes these endpoints:

### WHOOP

- `GET /v1/oauth/authorize` - Get OAuth authorization URL
- `GET /v1/oauth/callback` - OAuth callback (GET)
- `POST /v1/oauth/callback` - OAuth callback (POST, mobile)
- `POST /v1/webhooks/whoop` - Webhook handler
- `DELETE /v1/oauth/disconnect` - Disconnect user
- `GET /v1/data/{user_id}/recovery` - Fetch recovery data
- `GET /v1/data/{user_id}/sleep` - Fetch sleep data
- `GET /v1/data/{user_id}/workouts` - Fetch workout data
- `GET /v1/data/{user_id}/cycles` - Fetch cycle data

### Unified Service

- `GET /v1/whoop-cloud/oauth/authorize` - WHOOP OAuth
- `GET /v1/garmin-cloud/oauth/authorize` - Garmin OAuth
- `POST /v1/whoop-cloud/webhooks/whoop` - WHOOP webhooks
- `POST /v1/garmin-cloud/webhooks/garmin` - Garmin webhooks

### Health Check

- `GET /health` - Service health status

**API Docs:** http://localhost:8000/docs

## 🔒 Security

- **Token Storage**: DynamoDB with KMS encryption (production)
- **Dev Mode**: Tokens stored locally in `__dev__/tokens.json` (development)
- **Webhook Verification**: HMAC signature validation
- **Environment Variables**: Never commit `.env.local` files

## 🧪 Testing

```bash
# Run tests
pytest

# Run specific test
pytest tests/test_oauth.py -v

# Run with coverage
pytest --cov=server --cov-report=html
```

## 🐛 Troubleshooting

### ngrok Issues

**Problem:** "ngrok endpoint already online"

**Solution:**
```bash
# Kill all ngrok processes
pkill -f ngrok

# Or restart with different port
python3 wear.py start dev --port 8001
```

### Port Already in Use

**Problem:** "Port 8000 is already in use"

**Solution:**
```bash
# Find process using port
lsof -i :8000

# Kill process
kill $(lsof -ti :8000)

# Or use different port
python3 wear.py start dev --port 8001
```

### OAuth Flow Fails

**Problem:** "Authentication failed"

**Solution:**
1. Check environment variables in `.env.local`
2. Verify redirect URI matches vendor configuration
3. Check ngrok URL is correct
4. Look at server logs for detailed errors

## 📚 Internal Libraries

### py-cloud-connector

OAuth token management for wearable vendors with DynamoDB + KMS encryption.

**Features:**
- `VendorType`: Enum for supported vendors (whoop, garmin, fitbit)
- `TokenStore`: DynamoDB-based token storage with encryption
- `TokenSet`: Standardized OAuth token data structure

See [libs/py-cloud-connector/README.md](libs/py-cloud-connector/README.md)

### py-normalize

Data normalization utilities for converting vendor-specific formats to Synheart format.

**Features:**
- `DataNormalizer`: Converts vendor data to common format
- `DataType`: Enum for data types (recovery, sleep, workout, etc.)
- `NormalizedData`: Common data structure for all vendors

See [libs/py-normalize/README.md](libs/py-normalize/README.md)

## 🔗 Links

- **Main Repository**: [synheart-wear](https://github.com/synheart-ai/synheart-wear)
- **Flutter SDK**: [synheart-wear-dart](https://github.com/synheart-ai/synheart-wear-dart)
- **Android SDK**: [synheart-wear-kotlin](https://github.com/synheart-ai/synheart-wear-kotlin)
- **iOS SDK**: [synheart-wear-swift](https://github.com/synheart-ai/synheart-wear-swift)
- **ngrok**: https://ngrok.com/
- **Issues**: [GitHub Issues](https://github.com/synheart-ai/synheart-wear-cli/issues)

## 📄 License

MIT License - see [LICENSE](LICENSE) file

---

**Made with ❤️ by the Synheart AI Team**

*Technology with a heartbeat.*
