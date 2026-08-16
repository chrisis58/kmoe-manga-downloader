#!/usr/bin/env bash
# Install kmdr companion native messaging host — dev mode (Linux/macOS)
# Builds from local source, then delegates manifest + registry to install.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="$HOME/.local/share/kmdr-companion"
HOST_BIN="$INSTALL_DIR/native_host"

# Check Go
if ! command -v go &>/dev/null; then
  echo "ERROR: Go is not installed. Install from https://go.dev/dl/ and re-run."
  exit 1
fi

# Build (output to local dir so go build doesn't need full install path)
echo "Building native host from source..."
cd "$SCRIPT_DIR"
go build -v -o native_host
echo "  OK: $SCRIPT_DIR/native_host"

# Copy to install dir
mkdir -p "$INSTALL_DIR"
cp "$SCRIPT_DIR/native_host" "$HOST_BIN"

# Delegate manifest + registration to install.sh
exec "$SCRIPT_DIR/install.sh" --skip-download
