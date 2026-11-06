# KASPYRA Task 012 — authenticated store-and-forward transport prototype

This is an **experimental application-message transport**, not a satellite connection, CometBFT P2P transport replacement, or production-ready secure messaging system. It uses standard TCP over loopback by default. No hardware, provider, real RF, satellite path, or validator consensus integration is demonstrated.

## What is implemented

- Ed25519-signed envelopes with explicit public-key allowlisting, payload size and TTL limits.
- Durable SQLite outbound queue and inbound idempotency store.
- Length-framed TCP transfer, acknowledgements and retries after outages.
- Unit and real loopback socket tests for tampering, expiration, allowlisting, duplicates, persistence, outage and recovery.

## Run tests

`python -m pip install 'cryptography>=44,<47'`

`python -m unittest discover -s task012 -p 'test_*.py' -v`

## Manual two-process demonstration

From the repository root:

```
python task012/transport.py keygen /tmp/kaspyra-sender.key
# Put the printed public key (one per line) in /tmp/kaspyra-allowlist.txt
python task012/transport.py queue /tmp/kaspyra-out.db /tmp/kaspyra-sender.key 'hello from node A'
python task012/transport.py flush /tmp/kaspyra-out.db  # expected pending while receiver offline
# In another terminal:
python task012/transport.py receive /tmp/kaspyra-in.db /tmp/kaspyra-allowlist.txt
# Back in first terminal:
python task012/transport.py flush /tmp/kaspyra-out.db  # expected accepted
```

## Limitations and next gates

- No sender authentication at the socket layer; authentication applies to signed envelopes only. Do not expose this listener to the internet without network-level controls, rate limits, quotas, and review.
- No encryption/confidentiality; metadata and payload are visible to anyone on the path. Add authenticated encryption/mTLS for future external use.
- No automated retry scheduler, dead-letter handling, disk quota, key rotation, or monitoring.
- Acknowledgements are not authenticated; a malicious transport endpoint could forge acceptance. Do not treat delivery status as financial finality.
- SQLite single-process assumptions; no load or crash-injection validation.
- Only application-message transport. CometBFT consensus requires substantially different networking and timing analysis.
- Provider hardware, link budget, cost and path verification are **unresolved**. No GO for satellite-only claims.

## Integration

Files in this package are additive: `task012/` and `TASK_012_README.md`. Existing consensus and Task 010 remain unchanged. Upload the workflow separately into `.github/workflows/task012-transport.yml`.
