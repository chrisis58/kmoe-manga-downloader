#!/usr/bin/env bash
# Install kmdr companion native messaging host (Linux/macOS)
# Dev builds: use install-dev.sh instead
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="$HOME/.local/share/kmdr-companion"
REPO_OWNER="chrisis58"
REPO_NAME="kmoe-manga-downloader"
SKIP_DOWNLOAD=false

usage() {
  echo "Usage: $0"
  echo "  For local development builds, use install-dev.sh"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-download) SKIP_DOWNLOAD=true; shift ;;
    -h|--help) usage ;;
    *) shift ;;
  esac
done

# ── Detect OS/arch ────────────────────────────────────────────────

case "$(uname -s)" in
  Linux*)  OS="linux" ;;
  Darwin*) OS="darwin" ;;
  *) echo "Unsupported OS: $(uname -s)"; exit 1 ;;
esac

case "$(uname -m)" in
  x86_64|amd64) ARCH="amd64" ;;
  aarch64|arm64) ARCH="arm64" ;;
  *) echo "Unsupported architecture: $(uname -m)"; exit 1 ;;
esac

# ── Browser manifest directory ────────────────────────────────────

case "$(uname -s)" in
  Linux*)
    if [ -d "$HOME/.config/microsoft-edge" ]; then
      MANIFEST_DIR="$HOME/.config/microsoft-edge/NativeMessagingHosts"
    elif [ -d "$HOME/.config/google-chrome" ]; then
      MANIFEST_DIR="$HOME/.config/google-chrome/NativeMessagingHosts"
    elif [ -d "$HOME/.config/chromium" ]; then
      MANIFEST_DIR="$HOME/.config/chromium/NativeMessagingHosts"
    else
      MANIFEST_DIR="$HOME/.config/google-chrome/NativeMessagingHosts"
    fi
    ;;
  Darwin*)
    if [ -d "$HOME/Library/Application Support/Microsoft Edge" ]; then
      MANIFEST_DIR="$HOME/Library/Application Support/Microsoft Edge/NativeMessagingHosts"
    else
      MANIFEST_DIR="$HOME/Library/Application Support/Google/Chrome/NativeMessagingHosts"
    fi
    ;;
esac

# ── Create install dir ────────────────────────────────────────────

mkdir -p "$INSTALL_DIR"

HOST_BIN="$INSTALL_DIR/native_host"

# ── Download / verify binary ──────────────────────────────────────

if [ "$SKIP_DOWNLOAD" = false ]; then
  echo "Downloading native host..."
  ASSET="native_host-${OS}-${ARCH}"
  RELEASE_URL="https://github.com/${REPO_OWNER}/${REPO_NAME}/releases/latest/download/${ASSET}"
  echo "  ${RELEASE_URL}"

  if command -v curl &>/dev/null; then
    curl -fsSL "$RELEASE_URL" -o "$HOST_BIN" || {
      echo "  ERROR: Download failed."
      echo "  For local development, use: ./install-dev.sh"
      exit 1
    }
  elif command -v wget &>/dev/null; then
    wget -q "$RELEASE_URL" -O "$HOST_BIN" || {
      echo "  ERROR: Download failed."
      echo "  For local development, use: ./install-dev.sh"
      exit 1
    }
  else
    echo "  ERROR: curl or wget required to download."
    exit 1
  fi
else
  echo "Using existing binary: $HOST_BIN"
fi

if [ ! -f "$HOST_BIN" ]; then
  echo "  ERROR: $HOST_BIN not found"
  exit 1
fi

chmod +x "$HOST_BIN"
echo "  OK: $HOST_BIN"

# ── Extension ID ──────────────────────────────────────────────────

mkdir -p "$MANIFEST_DIR"

EXT_ID=""
if [ -f "$SCRIPT_DIR/extension/manifest.json" ]; then
  echo ""
  echo "Check your browser's extensions page for the extension ID."
  echo "It should be a 32-character string like: nhoopgfjhdholjmgklgbijmofpgbifhf"
fi

while [ -z "$EXT_ID" ] || [ ${#EXT_ID} -ne 32 ]; do
  read -p "Enter the 32-char extension ID: " EXT_ID
done

# ── Manifest ──────────────────────────────────────────────────────

MANIFEST_FILE="$MANIFEST_DIR/com.kmdr.host.json"
cat > "$MANIFEST_FILE" << JSONEOF
{
  "name": "com.kmdr.host",
  "description": "Kmoe Manga Downloader Native Messaging Host",
  "path": "$HOST_BIN",
  "type": "stdio",
  "allowed_origins": ["chrome-extension://$EXT_ID/"]
}
JSONEOF

# ── Done ──────────────────────────────────────────────────────────

echo ""
echo "✓ Native messaging host installed"
echo "  Manifest: $MANIFEST_FILE"
echo "  Host:     $HOST_BIN"
echo ""
echo "Next steps:"
echo "  1. Close browser completely (check for background processes)"
echo "  2. Load extension in browser's extensions page (Developer mode → Load unpacked)"
echo "  3. Verify extension ID matches: $EXT_ID"
