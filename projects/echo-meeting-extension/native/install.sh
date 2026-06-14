#!/usr/bin/env bash
# Install the Echo native messaging host for Chrome/Brave/Edge on macOS.
# Usage: ./install.sh <EXTENSION_ID>
# Get EXTENSION_ID from chrome://extensions (enable Developer mode, load the
# ../extension folder unpacked, copy the ID under the Echo card).
set -euo pipefail

EXT_ID="${1:-}"
if [[ -z "$EXT_ID" ]]; then
  echo "Usage: ./install.sh <EXTENSION_ID>"
  echo "Find the ID at chrome://extensions after loading ../extension unpacked."
  exit 1
fi

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOST_PY="$DIR/call_detector.py"
chmod +x "$HOST_PY"

NAME="com.echo.calldetector"
read -r -d '' MANIFEST <<JSON || true
{
  "name": "$NAME",
  "description": "Echo macOS call detector & recorder",
  "path": "$HOST_PY",
  "type": "stdio",
  "allowed_origins": [
    "chrome-extension://$EXT_ID/"
  ]
}
JSON

# Target dirs for common Chromium browsers.
TARGETS=(
  "$HOME/Library/Application Support/Google/Chrome/NativeMessagingHosts"
  "$HOME/Library/Application Support/Google/Chrome Beta/NativeMessagingHosts"
  "$HOME/Library/Application Support/BraveSoftware/Brave-Browser/NativeMessagingHosts"
  "$HOME/Library/Application Support/Microsoft Edge/NativeMessagingHosts"
  "$HOME/Library/Application Support/Arc/User Data/NativeMessagingHosts"
)

installed=0
for d in "${TARGETS[@]}"; do
  parent="$(dirname "$d")"
  if [[ -d "$parent" ]]; then
    mkdir -p "$d"
    printf '%s\n' "$MANIFEST" > "$d/$NAME.json"
    echo "Installed -> $d/$NAME.json"
    installed=1
  fi
done

# Seed config if missing.
mkdir -p "$HOME/.echo"
if [[ ! -f "$HOME/.echo/config.json" ]]; then
  cp "$DIR/config.example.json" "$HOME/.echo/config.json"
  echo "Created ~/.echo/config.json (edit it to add API keys + audio device)."
fi

if [[ "$installed" -eq 0 ]]; then
  echo "No supported browser profile found. Is Chrome installed?"
  exit 1
fi

echo
echo "Done. Restart the browser, then reload the Echo extension."
echo "Test detection: start a Zoom desktop meeting — you should get a 'Save it?' prompt."
echo "For desktop-call RECORDING you also need: brew install ffmpeg blackhole-2ch"
