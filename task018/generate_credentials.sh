#!/usr/bin/env bash
set -euo pipefail
IP="${1:-208.73.202.109}"
case "$IP" in 208.73.202.109) ;; *) echo 'Review IP SAN before generating credentials' >&2; exit 1;; esac
umask 077
D="$(pwd)/task018-private"
if [[ -e "$D" ]]; then echo "Refusing to overwrite existing $D" >&2; exit 1; fi
mkdir -m 700 "$D"
openssl req -x509 -newkey rsa:3072 -sha256 -nodes -days 2 -keyout "$D/ca.key" -out "$D/ca.pem" -subj '/CN=KASPYRA018 Ephemeral CA' >/dev/null 2>&1
openssl req -newkey rsa:3072 -nodes -keyout "$D/server.key" -out "$D/server.csr" -subj '/CN=kaspyra018-vps' >/dev/null 2>&1
printf 'subjectAltName=IP:%s\nextendedKeyUsage=serverAuth\n' "$IP" > "$D/server.ext"
openssl x509 -req -in "$D/server.csr" -CA "$D/ca.pem" -CAkey "$D/ca.key" -CAcreateserial -out "$D/server.pem" -days 2 -sha256 -extfile "$D/server.ext" >/dev/null 2>&1
openssl req -newkey rsa:3072 -nodes -keyout "$D/client.key" -out "$D/client.csr" -subj '/CN=kaspyra018-actions' >/dev/null 2>&1
printf 'extendedKeyUsage=clientAuth\n' > "$D/client.ext"
openssl x509 -req -in "$D/client.csr" -CA "$D/ca.pem" -CAkey "$D/ca.key" -CAcreateserial -out "$D/client.pem" -days 2 -sha256 -extfile "$D/client.ext" >/dev/null 2>&1
.venv/bin/python task016/field_link.py keygen "$D/message.key" >/dev/null
 .venv/bin/python - "$D/message.key" "$D/allowlist.txt" <<'PYCODE'
import sys
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
key=Ed25519PrivateKey.from_private_bytes(Path(sys.argv[1]).read_bytes())
pub=key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
Path(sys.argv[2]).write_text(pub.hex()+'\n')
PYCODE
chmod 600 "$D"/*
echo "Ephemeral credentials created in $D. Keep server.key and ca.key on VPS."
