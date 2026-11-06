# KASPYRA Task 021B — transaction bandwidth (research-only)

Runs four real CometBFT v0.38.17 validators in disposable Ubuntu GitHub Actions Linux network namespaces. Builds the existing task008c ABCI app unchanged and uses deterministic **test-only** Ed25519 keys to send real, signed application transfers. No production keys, funds, satellite links, or VPS networking involved.

## Measurements

- 20s empty-block baseline, then 20s each at offered 0.5, 1, and 2 transactions/sec.
- Synchronous `broadcast_tx_commit` with nonces spread across four funded test accounts. Only successful CheckTx and committed execution responses count.
- Validator-facing veth RX/TX bytes, 1-second approximate peak and p95 TX bits/s, achieved TPS, common height and matching block/app hashes.
- Recovery bytes measured only after restoring routes following a 15s outage (includes reconnection and new empty blocks, not queued transaction catch-up).

## Limitations

This is a bounded smoke benchmark, **not** a sustained-load capacity test, peak-line-rate measurement, proof of formal safety, or real satellite transport. Offered TPS may be constrained by synchronous RPC. Sampling misses subsecond bursts. The 4 deterministic keys are **never** safe for real assets. No actual satellite data pricing is implied.

## Running

The script **must not be run on a production VPS**. Commit and push the workflow, then use GitHub Actions to execute on a disposable hosted runner. Download `task021b-transaction-bandwidth-evidence` and inspect `task021b-bandwidth-evidence.json`. A failed workflow is an integration finding; preserve logs and do not mark it PASS.
