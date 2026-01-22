#!/usr/bin/env bash
set -euo pipefail

# Build synheart-flux Rust binary for use with wear-cli
#
# This script builds the `flux` executable and copies it into this repo's
# `./bin/` folder so it can be discovered via `server/flux_integration.py`.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLI_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FLUX_ROOT="${FLUX_ROOT:-$CLI_ROOT/../synheart-flux}"

if [ ! -d "$FLUX_ROOT" ]; then
    echo "Error: synheart-flux directory not found at: $FLUX_ROOT" >&2
    echo "Set FLUX_ROOT environment variable to point to synheart-flux directory" >&2
    exit 1
fi

echo "Building synheart-flux..."
cd "$FLUX_ROOT"

# Build release version
cargo build --release

# Determine platform
OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"

BIN_NAME="flux"
SRC_BIN="target/release/$BIN_NAME"

# Create output directory (repo-local)
OUT_DIR="$CLI_ROOT/bin"
mkdir -p "$OUT_DIR"

if [ ! -f "$SRC_BIN" ]; then
    echo "Error: flux binary not found at: $FLUX_ROOT/$SRC_BIN" >&2
    echo "Make sure synheart-flux builds a `flux` executable." >&2
    exit 1
fi

DEST_BIN="$OUT_DIR/flux"
cp -f "$SRC_BIN" "$DEST_BIN"
chmod +x "$DEST_BIN"
echo "✓ Copied flux binary to $DEST_BIN"

echo ""
echo "✅ Flux binary built successfully!"
echo "   Binary: $DEST_BIN"
echo ""
echo "You can now use Flux in the wear CLI."
