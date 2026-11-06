#!/usr/bin/env bash
set -euo pipefail
[[ "$(id -u)" == 0 ]] || { echo 'Run with sudo' >&2; exit 1; }
systemctl stop kaspyra018-forwarder.service kaspyra018-receiver.service 2>/dev/null || true
ufw --force delete allow 18443/tcp || true
ss -lnt | grep ':18443 ' && echo 'WARNING: port still listening' || true
