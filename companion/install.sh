#!/usr/bin/env bash
# Install kmdr companion native messaging host (Linux/macOS)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="$HOME/.local/share/kmdr-companion"
HOST_BIN="$INSTALL_DIR/native_host"
MANIFEST_TEMPLATE="$SCRIPT_DIR/manifest-template.json"

# Detect OS and set manifest dir
case "$(uname -s)" in
    Linux*)
        # Support Chrome, Chromium, and Edge
        if [ -d "$HOME/.config/microsoft-edge" ]; then
            MANIFEST_DIR="$HOME/.config/microsoft-edge/NativeMessagingHosts"
        elif [ -d "$HOME/.config/google-chrome" ]; then
            MANIFEST_DIR="$HOME/.config/google-chrome/NativeMessagingHosts"
        elif [ -d "$HOME/.config/chromium" ]; then
            MANIFEST_DIR="$HOME/.config/chromium/NativeMessagingHosts"
        else
            MANIFEST_DIR="$HOME/.config/google-chrome/NativeMessagingHosts"
        fi
        GOOS="linux"
        ;;
    Darwin*)
        MANIFEST_DIR="$HOME/Library/Application Support/Google/Chrome/NativeMessagingHosts"
        # Also support Edge on macOS
        if [ -d "$HOME/Library/Application Support/Microsoft Edge" ]; then
            MANIFEST_DIR="$HOME/Library/Application Support/Microsoft Edge/NativeMessagingHosts"
        fi
        GOOS="darwin"
        ;;
    *)
        echo "Unsupported OS: $(uname -s)"
        exit 1
        ;;
esac

# Detect architecture
ARCH=$(uname -m)
case "$ARCH" in
    x86_64|amd64)  GOARCH="amd64" ;;
    aarch64|arm64) GOARCH="arm64" ;;
    *)
        echo "Unsupported architecture: $ARCH"
        exit 1
        ;;
esac

# Create install directory
mkdir -p "$INSTALL_DIR"

# Build Go native host
echo "Building native host (${GOOS}/${GOARCH})..."
cd "$SCRIPT_DIR"
GOOS="$GOOS" GOARCH="$GOARCH" go build -o "$HOST_BIN" native_host.go
echo "  OK: $HOST_BIN"

# Create manifest directory
mkdir -p "$MANIFEST_DIR"

# Prompt for extension ID if needed
EXT_ID=""
if [ -f "$SCRIPT_DIR/extension/manifest.json" ]; then
    echo ""
    echo "Check your browser's extensions page for the extension ID."
    echo "It should be a 32-character string like: nhoopgfjhdholjmgklgbijmofpgbifhf"
fi

while [ -z "$EXT_ID" ] || [ ${#EXT_ID} -ne 32 ]; do
    read -p "Enter the 32-char extension ID: " EXT_ID
done

# Generate manifest with correct path
MANIFEST_FILE="$MANIFEST_DIR/com.kmdr.host.json"
python3 -c "
import json
with open('$MANIFEST_TEMPLATE') as f:
    m = json.load(f)
m['path'] = '$HOST_BIN'
m['allowed_origins'] = ['chrome-extension://$EXT_ID']
with open('$MANIFEST_FILE', 'w') as f:
    json.dump(m, f, indent=2)
"

echo ""
echo "✓ Native messaging host installed"
echo "  Manifest: $MANIFEST_FILE"
echo "  Host:     $HOST_BIN"
echo ""
echo "Next steps:"
echo "  1. Close browser completely (check for background processes)"
echo "  2. Load extension in browser's extensions page (Developer mode → Load unpacked)"
echo "  3. Verify extension ID matches: $EXT_ID"
