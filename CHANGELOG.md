# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-12-02

### Added

**🎉 Initial Release - Complete Local Development Tool for Cloud Wearables**

#### Core Features
- **Embedded FastAPI Server**: Local development server with automatic ngrok tunnel integration
- **Complete CLI Tool**: Command-line interface for managing OAuth tokens, pulling data, and inspecting webhooks
- **Multi-Vendor Support**: WHOOP, Garmin, and Fitbit cloud wearable integrations

#### OAuth & Authentication
- Complete OAuth 2.0 flows for cloud wearables (WHOOP, Garmin, Fitbit)
- Automatic token refresh and management
- Production-ready token storage with DynamoDB + KMS encryption
- Development mode with local token storage (no AWS required)

#### Data Management
- Real-time webhook endpoints for wearable data
- Data normalization to Synheart standard format
- Data pull commands for historical data retrieval
- Support for recovery, sleep, workout, and cycle data

#### Developer Experience
- Automatic ngrok tunnel creation for webhook testing
- Hot-reload support for development
- Comprehensive CLI commands:
  - `wear start dev` - Start local server with ngrok
  - `wear pull once` - Fetch data from cloud APIs
  - `wear tokens` - Manage OAuth tokens (list, refresh, revoke)
  - `wear webhook inspect` - Inspect recorded webhooks
- Built-in API documentation at `/docs`

#### Internal Libraries
- **py-cloud-connector**: OAuth token management, webhook verification, rate limiting
- **py-normalize**: Data normalization utilities for vendor-specific formats

#### Infrastructure
- PyPI publishing with GitHub Actions CI/CD
- Automated testing workflow (Linux, macOS, Windows)
- Trusted publishing setup (secure, no tokens needed)
- Comprehensive documentation (README, PUBLISHING guide, CHANGELOG)

#### Package Management
- Published to PyPI as `synheart-wear-cli`
- Simple installation: `pip install synheart-wear-cli`
- Python 3.11+ support
- All dependencies automatically installed

---

[0.1.0]: https://github.com/synheart-ai/synheart-wear-cli/releases/tag/v0.1.0
