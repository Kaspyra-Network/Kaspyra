# KASPYRA Task 010A — Satellite-style remote delivery

This phase exercises a **real local four-validator CometBFT network** with a controlled store-and-forward *client-to-RPC* relay. It tests a delayed uplink, a three-second complete client outage, one actual signed native transaction, duplicate suppression, expiry without submission, a subsequent valid transaction, account/nonce persistence, and canonical convergence.

**Not tested:** satellite hardware, RF links, Mars links, validator-to-validator latency/jitter, true asynchronous deep-space proofs, Byzantine safety. Validators remain normally connected. The relay is in-process and intentionally minimal; it is a test fixture, not production relay infrastructure. TTL is a relay policy, not an on-chain transaction expiration guarantee.

## GitHub upload (web UI)

1. Extract the ZIP and upload `task010/` and `TASK_010_README.md` to the **repository root**, preserving the `task010/` path.
2. Open the existing `.github/workflows/` directory in GitHub and upload the separately provided `task010a-network.yml` **there**.
3. Confirm the workflow `KASPYRA Task 010A Satellite-Style Delivery` runs.
4. Check for `PASS_PHASE_A` plus all four PASS experiment results.

## Running locally

Requires Go, CometBFT v0.38.17, Python 3.11+ and `cryptography`. Run `python task010/run_satellite_delivery.py` from repository root. Evidence written to `task010-result.json`.

## Next phase

Task 010B should introduce measured validator-to-validator delay/jitter and bounded communication windows using a controlled P2P proxy, with an explicit no-quorum safety gate and without conflating this with remote client delivery.
