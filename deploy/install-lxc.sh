#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/flight-alert}"
STATE_DIR="${STATE_DIR:-/var/lib/flight-alert}"
CONFIG_DIR="${CONFIG_DIR:-/etc/flight-alert}"
SERVICE_USER="${SERVICE_USER:-flight-alert}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run this installer as root inside the LXC." >&2
  exit 1
fi

if ! command -v apt-get >/dev/null || ! command -v systemctl >/dev/null; then
  echo "This installer supports Debian 12/Ubuntu 24.04 with apt and systemd." >&2
  exit 1
fi

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv python3-pip ca-certificates

if ! id "$SERVICE_USER" >/dev/null 2>&1; then
  useradd --system --home-dir "$APP_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
fi

install -d -o "$SERVICE_USER" -g "$SERVICE_USER" -m 0750 "$STATE_DIR"
install -d -o root -g "$SERVICE_USER" -m 0750 "$CONFIG_DIR"

if [[ ! -d "$APP_DIR" ]]; then
  echo "Application directory $APP_DIR does not exist. Copy the project there first." >&2
  exit 1
fi

python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/python" -m pip install --upgrade pip
"$APP_DIR/.venv/bin/pip" install "$APP_DIR"

if [[ ! -f "$CONFIG_DIR/flight-alert.env" ]]; then
  install -o root -g "$SERVICE_USER" -m 0600 "$APP_DIR/.env.example" "$CONFIG_DIR/flight-alert.env"
  echo "Created $CONFIG_DIR/flight-alert.env; edit Telegram credentials before production." >&2
fi

install -o root -g root -m 0644 "$APP_DIR/deploy/flight-alert.service" /etc/systemd/system/flight-alert.service
install -o root -g root -m 0644 "$APP_DIR/deploy/flight-alert.timer" /etc/systemd/system/flight-alert.timer
systemctl daemon-reload
systemctl enable flight-alert.timer

cat <<'EOF'
Installation complete.

Next steps:
  1. Edit /etc/flight-alert/flight-alert.env (keep mode 0600).
  2. Run: systemctl start flight-alert.service
  3. Inspect: journalctl -u flight-alert.service -n 100
  4. Enable schedule: systemctl start --now flight-alert.timer

Back up /var/lib/flight-alert/offers.db with the LXC backup. The installer only changes this container; it does not modify the Proxmox host.
EOF
