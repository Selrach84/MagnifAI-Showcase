#!/usr/bin/env bash
# One-shot installer for a fresh Ubuntu VPS (1 GB RAM friendly).
# Usage:  sudo bash scripts/install.sh
set -euo pipefail

APP_DIR=${APP_DIR:-/opt/receiptiq}
SERVICE=receiptiq

echo "==> Installing system deps"
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip rsync

echo "==> Syncing app to ${APP_DIR}"
mkdir -p "$APP_DIR"
rsync -a --exclude '.venv' --exclude 'data/*.db' "$(dirname "$0")/.." "$APP_DIR/"

echo "==> Creating virtualenv"
python3 -m venv "$APP_DIR/.venv"
# --no-cache-dir keeps disk + RAM use low during install
"$APP_DIR/.venv/bin/pip" install --no-cache-dir -U pip
"$APP_DIR/.venv/bin/pip" install --no-cache-dir -r "$APP_DIR/requirements.txt"

if [ ! -f "$APP_DIR/.env" ]; then
  cp "$APP_DIR/env.example" "$APP_DIR/.env"
  echo "==> Created $APP_DIR/.env  —  EDIT IT before starting (tokens, keys, SPREADSHEET_ID)."
fi

echo "==> Installing systemd service"
cp "$APP_DIR/systemd/${SERVICE}.service" "/etc/systemd/system/${SERVICE}.service"
systemctl daemon-reload
systemctl enable "$SERVICE"

cat <<EOF

✅ Installed.
Next:
  1. nano $APP_DIR/.env                # fill tokens/keys
  2. copy your Google service_account.json to $APP_DIR/
  3. share your spreadsheet with the service-account email (Editor)
  4. sudo systemctl start $SERVICE
  5. journalctl -u $SERVICE -f         # watch logs
EOF
