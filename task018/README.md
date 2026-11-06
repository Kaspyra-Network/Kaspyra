# KASPYRA Task 018 — VPS ↔ GitHub Actions field link

**Scope:** terrestrial public-internet test; NOT satellite routing. Uses existing `task012`, `task016`, `task017` from the GitHub repository. Does not run validators or touch Nginx/Docker.

## Preflight

VPS Ubuntu 26.04, public IP `208.73.202.109`. Port `18443` was not listening in the user's snapshot. VPS has high disk utilization and full swap; this test is short-lived. Do not run it if host health deteriorates. All commands below should be reviewed before running; do not paste private keys into chat or commit them.

## Step 1 — install files on VPS

Clone your own repository in a temporary directory (or upload the project files). Example:

```bash
sudo mkdir -p /opt/kaspyra-field-test
sudo chown "$USER":"$USER" /opt/kaspyra-field-test
cd /opt/kaspyra-field-test
git clone --depth 1 https://github.com/Kaspyra-Network/Kaspyra.git repo
cd repo
python3 -m venv .venv
.venv/bin/python -m pip install 'cryptography>=42,<47'
```

Use `task018/generate_credentials.sh` in this repository **on the VPS** to create an ephemeral CA and separate server/client certificates. The server certificate has an IP SAN for 208.73.202.109. Generated keys are stored under a restrictive `task018-private` directory. Never upload that directory to GitHub.

```bash
bash task018/generate_credentials.sh 208.73.202.109
```

## Step 2 — configure GitHub Actions secrets

In GitHub repository Settings → Secrets and variables → Actions, create these **repository secrets** by copying contents from the VPS **through your own secure administrative channel** (do not paste them into chat):

- `KASPYRA018_CA_PEM`: contents of `task018-private/ca.pem`
- `KASPYRA018_CLIENT_CERT_PEM`: contents of `task018-private/client.pem`
- `KASPYRA018_CLIENT_KEY_PEM`: contents of `task018-private/client.key`
- `KASPYRA018_SIGNING_KEY_PEM`: base64 encoding of `task018-private/message.key` (run `base64 -w0 task018-private/message.key` on the VPS)

`task018-private/server.key` and `task018-private/ca.key` MUST remain only on the VPS. Protect GitHub Actions secrets: only run the workflow from trusted repository branches; no pull_request trigger. Revoke/delete secrets after testing. The message signing key is test-only.

## Step 3 — start isolated VPS listeners

From repo root:

```bash
sudo bash task018/start_vps.sh
```

The script uses `systemd-run` transient units with CPU/memory/runtime limits, runs the Task 016 receiver on loopback and Task 017 mTLS forwarder on 0.0.0.0:18443. It temporarily adds UFW allow for 18443; the workflow runner source IP changes, so the port is internet-reachable but mTLS-authenticated. Confirm this exposure is acceptable before proceeding. Stop with `sudo bash task018/stop_vps.sh` as soon as the test finishes. The units have automatic expiry, but **UFW cleanup requires running the stop script**.

## Step 4 — run Actions

Run the workflow **KASPYRA Task 018 Remote VPS Field Test** using `workflow_dispatch` from your trusted main branch. It sends a harmless signed test message (NOT a blockchain transaction), records response status and timing, and uploads a sanitized JSON evidence file. The job does not assert a satellite path.

## Step 5 — cleanup and inspect

```bash
sudo bash task018/stop_vps.sh
sudo journalctl -u kaspyra018-receiver -u kaspyra018-forwarder --since '20 minutes ago' --no-pager
```

Delete the four Task 018 GitHub Actions secrets and remove `task018-private` after collecting evidence. Verify `sudo ufw status` no longer lists port 18443. Do not delete unrelated files or services.

## Acceptance gates

- Successful mTLS handshake with IP SAN verified
- Task 016 signed message accepted and persisted at receiver
- Sender response includes delivery timing and digest
- VPS logs confirm receiving test traffic
- No changes to existing services
- Clear labeling: terrestrial internet, not satellite

## Caveats

- The CI workflow cannot validate VPS access until credentials and listener are configured.
- No guarantee of real satellite transport or validator P2P integration.
- If systemd transient units fail, do not weaken the resource limits; report logs.
