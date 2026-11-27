#!/usr/bin/env bash
# Flight Alert - Proxmox LXC installer
# Eseguire dal nodo Proxmox: bash <(curl -fsSL https://raw.githubusercontent.com/0rsobiond0/flight-alert/main/deploy/proxmox-create-lxc.sh)

set -euo pipefail

# ── Colori ────────────────────────────────────────────────────────────────────
YW="\e[33m"; GN="\e[32m"; RD="\e[31m"; CL="\e[0m"; BL="\e[36m"; CM="\e[0m"
header_info() { echo -e "${BL}
╔═══════════════════════════════════════╗
║        Flight Alert LXC Setup         ║
║   Bot voli Milano → Telegram alerts   ║
╚═══════════════════════════════════════╝${CL}"; }

msg()  { echo -e "${GN}✔ ${CL}$1"; }
warn() { echo -e "${YW}⚠ ${CL}$1"; }
err()  { echo -e "${RD}✘ ${CL}$1" >&2; exit 1; }
ask()  { echo -e "${YW}? ${CL}$1"; }

# ── Requisiti ─────────────────────────────────────────────────────────────────
[[ "$(id -u)" -ne 0 ]] && err "Eseguire come root sul nodo Proxmox"
command -v pct >/dev/null || err "pct non trovato: questo script va eseguito sul nodo Proxmox"

header_info

# ── Configurazione interattiva ────────────────────────────────────────────────
ask "ID del container (default: prossimo disponibile):"
read -r CT_ID
if [[ -z "$CT_ID" ]]; then
  CT_ID=$(pvesh get /cluster/nextid 2>/dev/null || echo "200")
fi

ask "Nome host del container (default: flight-alert):"
read -r CT_HOSTNAME
CT_HOSTNAME="${CT_HOSTNAME:-flight-alert}"

ask "RAM in MB (default: 1024):"
read -r CT_RAM
CT_RAM="${CT_RAM:-1024}"

ask "Disco in GB (default: 4):"
read -r CT_DISK
CT_DISK="${CT_DISK:-4}"

ask "Bridge di rete (default: vmbr0):"
read -r CT_BRIDGE
CT_BRIDGE="${CT_BRIDGE:-vmbr0}"

ask "IP (es. 192.168.1.50/24) oppure invio per DHCP:"
read -r CT_IP

ask "Password root del container:"
read -rs CT_PASSWORD
echo
[[ -z "$CT_PASSWORD" ]] && err "La password non può essere vuota"

echo
ask "Token Telegram del bot (da @BotFather):"
read -r TG_TOKEN
ask "Chat ID Telegram (il tuo ID utente):"
read -r TG_CHAT_ID

echo
ask "Budget massimo in EUR per 2 persone (default: 100):"
read -r MAX_EUR
MAX_EUR="${MAX_EUR:-100}"

ask "Durata minima soggiorno in notti (default: 2):"
read -r MIN_NIGHTS
MIN_NIGHTS="${MIN_NIGHTS:-2}"

ask "Durata massima soggiorno in notti (default: 4):"
read -r MAX_NIGHTS
MAX_NIGHTS="${MAX_NIGHTS:-4}"

ask "Data di fine ricerca YYYY-MM-DD (default: 2027-03-31):"
read -r SEARCH_UNTIL
SEARCH_UNTIL="${SEARCH_UNTIL:-2027-03-31}"

# ── Trova storage e template ───────────────────────────────────────────────────
echo
msg "Cerco storage disponibile..."
STORAGE=$(pvesm status -content rootdir 2>/dev/null | awk 'NR>1 && $3=="active" {print $1; exit}')
[[ -z "$STORAGE" ]] && STORAGE="local-lvm"
msg "Uso storage: $STORAGE"

msg "Cerco template Debian 12..."
TEMPLATE=$(pveam list local 2>/dev/null | grep -i "debian-12" | awk '{print $1}' | head -1)
if [[ -z "$TEMPLATE" ]]; then
  msg "Template non trovato, scarico Debian 12..."
  pveam update >/dev/null 2>&1
  AVAILABLE=$(pveam available --section system 2>/dev/null | grep -i "debian-12" | awk '{print $2}' | head -1)
  [[ -z "$AVAILABLE" ]] && err "Impossibile trovare un template Debian 12"
  pveam download local "$AVAILABLE" >/dev/null 2>&1
  TEMPLATE="local:vztmpl/$AVAILABLE"
  msg "Template scaricato: $AVAILABLE"
else
  msg "Template trovato: $TEMPLATE"
fi

# ── Crea il container ─────────────────────────────────────────────────────────
msg "Creo container LXC $CT_ID ($CT_HOSTNAME)..."
NET_CONFIG="name=eth0,bridge=${CT_BRIDGE}"
if [[ -n "$CT_IP" ]]; then
  # Estrai gateway dall'IP (es. 192.168.1.50/24 → 192.168.1.1)
  GW=$(echo "$CT_IP" | awk -F'[./]' '{print $1"."$2"."$3".1"}')
  ask "Gateway (default: $GW):"
  read -r CT_GW
  CT_GW="${CT_GW:-$GW}"
  NET_CONFIG="${NET_CONFIG},ip=${CT_IP},gw=${CT_GW}"
else
  NET_CONFIG="${NET_CONFIG},ip=dhcp"
fi

pct create "$CT_ID" "$TEMPLATE" \
  --hostname "$CT_HOSTNAME" \
  --password "$CT_PASSWORD" \
  --memory "$CT_RAM" \
  --rootfs "${STORAGE}:${CT_DISK}" \
  --net0 "$NET_CONFIG" \
  --unprivileged 1 \
  --features nesting=1 \
  --start 1 \
  --ostype debian

msg "Container creato e avviato"
sleep 3

# ── Installa software nel container ───────────────────────────────────────────
msg "Installo dipendenze nel container..."
pct exec "$CT_ID" -- bash -c "
  set -euo pipefail
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq git python3 python3-venv python3-pip ca-certificates
"

# ── Clona il repository ───────────────────────────────────────────────────────
msg "Clono flight-alert da GitHub..."
pct exec "$CT_ID" -- bash -c "
  git clone --quiet https://github.com/0rsobiond0/flight-alert /opt/flight-alert
"

# ── Crea utente e directory ───────────────────────────────────────────────────
msg "Configuro utente e directory..."
pct exec "$CT_ID" -- bash -c "
  set -euo pipefail
  useradd --system --home-dir /opt/flight-alert --shell /usr/sbin/nologin flight-alert 2>/dev/null || true
  mkdir -p /var/lib/flight-alert /etc/flight-alert
  chown flight-alert:flight-alert /var/lib/flight-alert
  chmod 750 /var/lib/flight-alert /etc/flight-alert
  python3 -m venv /opt/flight-alert/.venv
  /opt/flight-alert/.venv/bin/pip install -q /opt/flight-alert
"

# ── Scrivi configurazione ─────────────────────────────────────────────────────
msg "Scrivo configurazione..."
pct exec "$CT_ID" -- bash -c "cat > /etc/flight-alert/flight-alert.env" <<EOF
ORIGINS=MXP,BGY,LIN
PASSENGERS=2
MIN_NIGHTS=${MIN_NIGHTS}
MAX_NIGHTS=${MAX_NIGHTS}
MAX_TOTAL_EUR=${MAX_EUR}
SEARCH_UNTIL=${SEARCH_UNTIL}
CHECK_INTERVAL_HOURS=6
PROVIDER=ryanair
STATE_DB=/var/lib/flight-alert/offers.db
DRY_RUN=false
TELEGRAM_BOT_TOKEN=${TG_TOKEN}
TELEGRAM_CHAT_ID=${TG_CHAT_ID}
EOF
pct exec "$CT_ID" -- chmod 600 /etc/flight-alert/flight-alert.env
pct exec "$CT_ID" -- chown root:flight-alert /etc/flight-alert/flight-alert.env

# ── Installa systemd units ────────────────────────────────────────────────────
msg "Installo servizi systemd..."
pct exec "$CT_ID" -- bash -c "
  cp /opt/flight-alert/deploy/flight-alert.service /etc/systemd/system/
  cp /opt/flight-alert/deploy/flight-alert.timer /etc/systemd/system/
  systemctl daemon-reload
  systemctl enable flight-alert.timer
"

# ── Prima esecuzione di test ──────────────────────────────────────────────────
msg "Eseguo primo ciclo di ricerca (dry-run)..."
pct exec "$CT_ID" -- bash -c "
  source /etc/flight-alert/flight-alert.env
  DRY_RUN=true /opt/flight-alert/.venv/bin/python -m flight_alert --once --dry-run 2>&1 | tail -3
" || warn "Il primo test ha avuto un problema; controlla i log con: pct exec ${CT_ID} -- journalctl -u flight-alert.service -n 50"

# ── Avvia il timer ────────────────────────────────────────────────────────────
msg "Avvio timer..."
pct exec "$CT_ID" -- systemctl start flight-alert.timer

# ── Fine ──────────────────────────────────────────────────────────────────────
CT_IP_ACTUAL=$(pct exec "$CT_ID" -- hostname -I 2>/dev/null | awk '{print $1}' || echo "n/d")
echo
echo -e "${GN}╔══════════════════════════════════════════╗"
echo -e "║          Installazione completata!       ║"
echo -e "╠══════════════════════════════════════════╣"
echo -e "║  Container:  CT ${CT_ID} (${CT_HOSTNAME})            "
echo -e "║  IP:         ${CT_IP_ACTUAL}                      "
echo -e "║  Cerca ogni 6 ore, notifica su Telegram  ║"
echo -e "║  Budget:     <= ${MAX_EUR} EUR per 2 persone      "
echo -e "╠══════════════════════════════════════════╣"
echo -e "║  Log:  pct exec ${CT_ID} -- journalctl -u        "
echo -e "║        flight-alert.service -n 50        ║"
echo -e "╚══════════════════════════════════════════╝${CL}"
