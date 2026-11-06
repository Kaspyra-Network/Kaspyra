#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
D="$(pwd)/task018-private"
[[ -s "$D/server.key" && -s "$D/allowlist.txt" ]] || { echo 'Run generate_credentials.sh first' >&2; exit 1; }
[[ "$(id -u)" == 0 ]] || { echo 'Run with sudo from repo root; root must be able to read credentials' >&2; exit 1; }
[[ ! -e /run/systemd/system/kaspyra018-receiver.service ]] || { echo 'Already running' >&2; exit 1; }
if ss -lnt | grep -qE '[:.]18443[[:space:]]'; then echo 'Port 18443 occupied' >&2; exit 1; fi
systemd-run --unit=kaspyra018-receiver --property=RuntimeMaxSec=900 --property=MemoryMax=128M --property=CPUQuota=20% --property=NoNewPrivileges=yes --property=WorkingDirectory="$(pwd)" -- "$(pwd)/.venv/bin/python" task016/field_link.py listen "$D/inbox.db" "$D/allowlist.txt" --host 127.0.0.1 --port 18716
systemd-run --unit=kaspyra018-forwarder --property=RuntimeMaxSec=900 --property=MemoryMax=128M --property=CPUQuota=20% --property=NoNewPrivileges=yes --property=WorkingDirectory="$(pwd)" -- "$(pwd)/.venv/bin/python" task017/secure_link.py server --bind 0.0.0.0 --port 18443 --upstream-host 127.0.0.1 --upstream-port 18716 --ca "$D/ca.pem" --cert "$D/server.pem" --key "$D/server.key"
ufw allow 18443/tcp comment 'KASPYRA018 temporary mTLS test'
echo 'Started temporary units; remove firewall rule with task018/stop_vps.sh after test.'
